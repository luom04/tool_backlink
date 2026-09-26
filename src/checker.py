"""
Backlink Checker v3 - dieu khien hoan toan bang file cau hinh YAML.

Moi tham so (money site, so tang, tang nao tro ve dau, concurrency, delay,
domain nao bat buoc render JS...) nam trong config/<site>.yaml.

Chay:
    python src/checker.py -c config/checkbacklink.yaml --tier 1 --limit 20
    python src/checker.py -c config/checkbacklink.yaml --tier 1
    python src/checker.py -c config/checkbacklink.yaml --tier 3 --js
    python src/checker.py -c config/checkbacklink.yaml --all

Ket qua: results/<ngay>_<site>_tier<N>.csv  va  .xlsx (co to mau).
"""

import argparse
import asyncio
import csv
import re
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict, fields
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
import bl_config
import diagnose as D
import dnsfix
import robotscheck
import urlutil as U

HOMEPAGE_PATHS = ("", "/", "/index.html", "/index.php", "/home", "/home/")


@dataclass
class Result:
    stt: str = ""
    tier: str = ""
    sheet: str = ""
    source_url: str = ""
    status: str = ""          # FOUND / NOT_FOUND / PAGE_ERROR
    http_code: str = ""
    final_url: str = ""
    points_to: str = ""
    khop_tang: str = ""       # link roi vao tang nao: money / tier 2 / tier 3...
    anchor_text: str = ""
    rel: str = ""
    indexable: str = ""
    rendered: str = ""        # http / playwright
    robots: str = ""          # cho phep / bi chan / khong ro - theo robots.txt
    # Hai goc nhin dat canh nhau: nguoi mo trang bang trinh duyet thay gi, va
    # Googlebot thay gi. Tool KET LUAN theo Googlebot - Google chi truyen gia
    # tri qua nhung gi no nhin thay. Hai cot lech nhau la dau hieu cloaking.
    nguoi_xem: str = ""
    googlebot: str = ""
    # URL tang tren ma link nay do vao con song khong. Link tang 3 con nguyen
    # ma URL tang 2 no tro toi da chet thi gia tri dung lai o do.
    dich_tang_tren: str = ""
    vi_tri_link: str = ""     # than bai / binh luan / sidebar / footer / ho so...
    elapsed: str = ""
    ket_luan: str = ""        # SONG / MAT / CHECK_TAY
    yeu_cau: str = ""         # Thay link moi / Sua link - chi dien khi can xu ly
    cach_xu_ly: str = ""      # chi dien khi ket_luan = CHECK_TAY
    huong_dan_check: str = ""
    diag_code: str = ""
    severity: str = ""
    muc_do: str = ""
    chan_doan: str = ""
    viec_can_lam: str = ""
    canh_bao_them: str = ""
    note: str = ""
    checked_at: str = ""


# ------------------------------------------------------------------ phan tich
# Chi thi robots co gia tri dang sau dau hai cham - KHONG phai ten bot.
# "unavailable_after: 25 Jun 2026" la mot chi thi, con "bingbot: noindex" thi
# "bingbot" la ten bot. Nham hai loai nay la bo sot noindex hoac bao noindex oan.
CHI_THI_CO_GIA_TRI = ("unavailable_after", "max-snippet", "max-image-preview",
                      "max-video-preview")


def _chi_thi_header(values):
    """Doc cac header X-Robots-Tag, chi giu chi thi co hieu luc voi Googlebot.

    Mot header co the viet cho moi bot ("noindex, nofollow") hoac cho rieng
    mot bot ("googlebot: noindex" / "bingbot: noindex"). Ten bot dung dau ap
    dung cho moi chi thi phia sau trong cung header do.
    """
    out = set()
    for value in values or []:
        bot = None
        for phan in str(value).split(","):
            phan = phan.strip().lower()
            if not phan:
                continue
            if ":" in phan:
                truoc, sau = (x.strip() for x in phan.split(":", 1))
                if truoc not in CHI_THI_CO_GIA_TRI:
                    bot, phan = truoc, sau
            if phan and (bot is None or "googlebot" in bot):
                out.add(phan)
    return out


def _chi_thi_robots(soup, x_robots):
    """Gom chi thi robots ma Googlebot phai tuan theo -> (tap chi thi, nguon).

    Truoc day chi doc <meta name="robots">. Bo sot hai duong Google van doc:
      <meta name="googlebot" content="noindex">  - viet rieng cho Google
      header HTTP X-Robots-Tag: noindex           - khong nam trong HTML
    Ca hai deu cho ra "Link con" sai.
    """
    chi_thi, nguon = set(), []
    for m in soup.find_all("meta", attrs={"name": True}):
        ten = (m.get("name") or "").strip().lower()
        if ten not in ("robots", "googlebot"):
            continue
        cs = {x.strip().lower() for x in (m.get("content") or "").split(",")
              if x.strip()}
        if cs & {"noindex", "nofollow", "none"}:
            nguon.append("meta %s" % ten)
        chi_thi |= cs
    tu_header = _chi_thi_header(x_robots)
    if tu_header & {"noindex", "nofollow", "none"}:
        nguon.append("X-Robots-Tag")
    return chi_thi | tu_header, nguon


# Kieu an phan tu viet thang tren the (inline). Class CSS dat trong file .css
# thi HTML khong cho biet - day la gioi han cua cach doc nay.
AN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|"
    r"font-size\s*:\s*0+(?:\.0+)?(?:px|pt|em|rem|%)?\s*(?:;|!|$)|"
    r"(?:text-indent|left|top)\s*:\s*-\d{3,}", re.I)


def _bi_an(a):
    """The <a> co nam trong phan tu bi an bang style inline / thuoc tinh hidden."""
    for el in [a] + list(a.parents):
        if getattr(el, "name", None) in (None, "[document]"):
            break
        if el.has_attr("hidden") or AN_STYLE.search(el.get("style") or ""):
            return True
    return False


# Vi tri link: phan tu cha GAN NHAT quyet dinh. Di het len tan goc roi de ket
# qua ghi de nhau thi link trong khung binh luan nam trong <article> bi bao la
# "than bai". Tu khoa so theo tung manh cua id/class, khong so chuoi con -
# "domain" khong duoc khop "main", "canvas" khong duoc khop "nav".
VI_TRI_THE = {"footer": "footer", "nav": "menu", "aside": "sidebar",
              "header": "dau trang", "article": "than bai", "main": "than bai"}
VI_TRI_TU = (
    ("binh luan", ("comment", "comments", "reply", "respond", "disqus")),
    ("ho so", ("profile", "author", "bio", "member", "user", "vcard")),
    ("footer", ("footer",)),
    ("sidebar", ("sidebar",)),
    ("menu", ("menu", "nav", "navbar", "navigation", "breadcrumb")),
    ("than bai", ("article", "content", "post", "entry", "main", "story")),
)


def _vi_tri(a):
    # "widget" co o ca sidebar lan footer, nen chi la goi y yeu: di tiep len
    # tren, gap footer/aside thi theo do, het cay moi coi la sidebar.
    du_phong = None
    for el in a.parents:
        ten = getattr(el, "name", None)
        if ten in (None, "[document]", "html", "body"):
            break
        manh = [m for m in re.split(r"[^a-z0-9]+", " ".join(
            [el.get("id") or ""] + list(el.get("class") or [])).lower()) if m]
        for nhan, tus in VI_TRI_TU:
            if any(m == t or m.startswith(t) for m in manh for t in tus):
                return nhan
        if du_phong is None and any(m.startswith("widget") for m in manh):
            du_phong = "sidebar"
        if ten in VI_TRI_THE:
            return VI_TRI_THE[ten]
    return du_phong or "khong ro"


def analyse(html, final_url, res, target_norms, target_domains,
            declared_label="", x_robots=None):
    """Doc HTML, dien vao res, tra ve dict tin hieu tho cho module chan doan.

    x_robots: danh sach gia tri header X-Robots-Tag cua response (neu co).
    """
    soup = BeautifulSoup(html, "lxml")
    page = {}

    page["title"] = (soup.title.get_text(strip=True) if soup.title else "")[:300]
    body = soup.body or soup
    text = body.get_text(" ", strip=True)
    page["text_len"] = len(text)
    page["snippet"] = text[:1500]

    chi_thi, nguon_robots = _chi_thi_robots(soup, x_robots)
    noindex = bool(chi_thi & {"noindex", "none"})
    # nofollow cap trang: moi link tren trang deu nofollow du the <a> khong co rel.
    nofollow_trang = bool(chi_thi & {"nofollow", "none"})
    canon = soup.find("link", rel=lambda v: v and "canonical" in v)
    canon_ok = True
    if canon and canon.get("href"):
        canon_ok = U.normalize(urljoin(final_url, canon["href"])) == U.normalize(final_url)
    res.indexable = "no" if (noindex or not canon_ok) else "yes"
    if noindex:
        res.note = ("noindex (%s)" % ", ".join(nguon_robots)) if nguon_robots else "noindex"
    elif not canon_ok:
        res.note = "canonical khac"

    # <base href> doi goc cua moi href tuong doi tren trang.
    base = soup.find("base", href=True)
    goc = urljoin(final_url, base["href"]) if base else final_url

    src_host = U.domain_of(final_url)
    outbound = 0
    ung_vien = []

    for thu_tu, a in enumerate(soup.find_all("a", href=True)):
        raw_href = a["href"]
        href = urljoin(goc, raw_href)
        if U.domain_of(href) not in ("", src_host):
            outbound += 1
        hn = U.normalize(href)
        if hn in target_norms:
            hang, label = 0, target_norms[hn]
        elif U.domain_of(href) in target_domains:
            hang, label = 1, target_domains[U.domain_of(href)]
        else:
            continue
        ung_vien.append((hang, thu_tu, a, href, raw_href, label))

    page["outbound"] = outbound
    page["so_link_ve_dich"] = len(ung_vien)
    if not ung_vien:
        res.status = "NOT_FOUND"
        return False, page

    def _rel(a):
        return " ".join(a.get("rel") or []).lower() or "dofollow"

    # Trang co nhieu link ve dich thi chon link TOT NHAT, khong lay link dau tien:
    # dung URL truoc sai URL, dofollow truoc nofollow, hien truoc an. Lay link dau
    # tien thi mot link nofollow o sidebar dung truoc link dofollow trong bai se
    # bien ca dong thanh NOFOLLOW - tinh vao yeu cau bu oan.
    xep = sorted(ung_vien, key=lambda x: (
        x[0], any(r in _rel(x[2]) for r in D.NOFOLLOW_REL), _bi_an(x[2]), x[1]))
    hang, _tt, a, href, raw_href, label = xep[0]

    anchor = " ".join(a.get_text(" ", strip=True).split())[:150]
    if not anchor:
        img = a.find("img")
        alt = " ".join((img.get("alt") or "").split())[:140] if img else ""
        # Link la anh: anchor that su chinh la thuoc tinh alt.
        anchor = ("(anh) " + alt) if alt else ""
    rel = _rel(a)
    if nofollow_trang and not any(r in rel for r in D.NOFOLLOW_REL):
        rel = "%s | nofollow toan trang (%s)" % (rel, ", ".join(nguon_robots))

    res.status, res.points_to = "FOUND", href
    res.anchor_text = anchor or "(anh / rong)"
    res.rel = rel
    res.khop_tang = label
    page["khop_tang"] = label
    page["tang_khai_bao"] = declared_label
    page["sai_tang"] = bool(declared_label) and label != declared_label
    # "Khop domain nhung sai URL dich" chi co nghia khi DA khai URL dich cu the
    # cho ten mien do. Khai 'target_urls' rong = chi can tro dung domain la dat,
    # trang nao cung duoc - luc do bao sai URL la bao oan toan bo danh sach.
    sai_url = hang == 1 and any(U.domain_of(u) == U.domain_of(href)
                                for u in target_norms)
    page["domain_only_match"] = sai_url
    page["link_bi_an"] = _bi_an(a)
    page["vi_tri"] = _vi_tri(a)
    if sai_url:
        res.note = (res.note + "; " if res.note else "") + "khop domain, sai URL dich"
    page["via_redirect"] = D.via_redirect(raw_href, href)
    return True, page


# Ma HTTP cho thay may chu tu choi *cach doc*, khong phai trang da chet.
# Chromium that thuong di qua duoc, nen day sang luot render truoc khi ket luan.
HTTP_DANG_NGO = (401, 403, 405, 406, 429, 500, 502, 503)


def _nen_render(cfg, dom, use_js, page, http_code=None, loi_ket_noi=False):
    """Co dua link nay sang luot render bang Chromium khong?

    Luot 1 doc HTML tho cho toan bo danh sach. Chi nhung link co dau hieu
    "chua doc duoc noi dung that" moi tra gia mo trinh duyet o luot 2.
    """
    if cfg.force_js_domain(dom) or use_js:
        return True
    if not cfg.js.get("escalate", True):
        return False
    if loi_ket_noi:
        # DNS khong phan giai duoc thi trinh duyet cung chiu, khoi mat cong.
        err = (page.get("error") or "").lower()
        return not any(k in err for k in
                       ("getaddrinfo", "name or service", "nodename", "dns"))
    if http_code is not None:
        return int(http_code) in HTTP_DANG_NGO
    # Con lai: luot 1 doc duoc trang nhung khong thay the <a> nao ve dich.
    # Luon thu lai bang Chromium truoc khi dam ket luan la mat link - day chinh
    # la truong hop tung cho ra hang loat LINK_BI_GO gia o tier 1 va 2.
    return True


# Ma HTTP cho thay link da mat han - hoi robots.txt them cung khong doi duoc gi.
CHET_HAN = ("404", "410")


def _bo_qua_robots(res, page):
    """Co bo qua buoc doc robots.txt cho dong nay khong?

    Bo qua khi trang da chet han (404/410) hoac ten mien khong phan giai duoc -
    tiet kiem mot request tren dung nhung host chac chan khong tra loi.
    """
    if res.http_code in CHET_HAN:
        return True
    err = (page.get("error") or "").lower()
    return any(k in err for k in ("getaddrinfo", "name or service", "nodename", "dns"))


def _redirect_flags(source_url, final_url, page):
    if not final_url:
        return
    s, f = urlparse(source_url), urlparse(final_url)
    if U.registrable(source_url) != U.registrable(final_url):
        page["redirected_off_domain"] = True
    elif (s.path or "/").rstrip("/") not in ("", "/") \
            and (f.path or "/").lower() in HOMEPAGE_PATHS:
        page["redirected_to_home"] = True


# ------------------------------------------------------------------ chay check
async def check_one(client, row, sem, locks, targets, js_queue, cfg, use_js,
                    on_progress=None, quiet=False, robots=None, vadns=None):
    res = Result(stt=row["stt"], tier=row["tier"], sheet=row["sheet"],
                 source_url=row["source_url"],
                 checked_at=datetime.now().strftime("%Y-%m-%d %H:%M"))
    tnorm, tdom, tlabel = targets[str(row["tier"])]
    dom = U.domain_of(res.source_url)
    page, t0 = {}, time.monotonic()
    retries = int(cfg.network.get("retries", 1))

    async with sem:
        # Kiem tra DNS TRUOC khi tai trang. Neu router tra ve 127.0.0.1 thi
        # request se di vao chinh may nay - hoac bi tu choi (on ao), hoac te
        # hon la duoc mot web server nao do tren may tra loi thay, cho ra
        # LINK_BI_GO gia. Xem dnsfix.py.
        if vadns is not None:
            await vadns.dam_bao(client, dom)
        async with locks[dom]:
            for attempt in range(retries + 1):
                try:
                    r = await client.get(res.source_url, follow_redirects=True)
                    res.http_code = str(r.status_code)
                    res.final_url = str(r.url)
                    res.rendered = "http"
                    _redirect_flags(res.source_url, res.final_url, page)
                    ctype = r.headers.get("content-type", "").lower()
                    if r.status_code >= 400:
                        res.status, res.note = "PAGE_ERROR", "HTTP %s" % r.status_code
                        page["snippet"] = r.text[:1500]
                        if _nen_render(cfg, dom, use_js, page, r.status_code):
                            res._queued_js = True
                            js_queue.append((res, tnorm, tdom, tlabel, page))
                    elif "html" not in ctype and "xml" not in ctype:
                        res.status, res.note = "PAGE_ERROR", "content-type: %s" % ctype[:40]
                        page["not_html"] = True
                    else:
                        ok, page2 = analyse(r.text, res.final_url, res,
                                            tnorm, tdom, tlabel,
                                            x_robots=r.headers.get_list("x-robots-tag"))
                        page.update(page2)
                        if not ok and _nen_render(cfg, dom, use_js, page):
                            res._queued_js = True
                            js_queue.append((res, tnorm, tdom, tlabel, page))
                    break
                except httpx.TimeoutException:
                    res.status, res.note = "PAGE_ERROR", "timeout"
                    page["error"] = "timeout"
                    # KHONG thu lai sau timeout. Mot lan timeout da tra tron
                    # network.timeout giay; ban lai y het thao tac vua that bai
                    # hiem khi doi duoc ket qua, ma tra gia dat nhat trong ca
                    # dot chay. Link nay van con mot luot thu nua: khoi lenh
                    # ngay ben duoi day no sang Chromium o luot 2, va trinh
                    # duyet that manh hon httpx lap lai nhieu.
                    break
                except httpx.TooManyRedirects:
                    # Trang chuyen huong vong tron. Khong phai loi mang nen thu lai
                    # vo ich; van de Chromium thu mot luot (co site chi lap voi
                    # client khong giu cookie), that bai nua moi ket luan.
                    res.status, res.note = "PAGE_ERROR", "chuyen huong vong tron"
                    page["error"] = "TooManyRedirects"
                    page["vong_lap"] = True
                    break
                except Exception as e:
                    res.status = "PAGE_ERROR"
                    res.note = type(e).__name__
                    page["error"] = "%s: %s" % (type(e).__name__, e)[:200]
                # Con lai la loi ket noi (ConnectError, ReadError, SSL...):
                # that bai trong duoi mot giay nen thu lai gan nhu mien phi, va
                # phan lon la nghen mang chop nhoang - ty le cuu duoc cao.
                if attempt < retries:
                    await asyncio.sleep(cfg.network["per_domain_delay"])

            # Va DNS roi ma van khong ket noi duoc: duong truyen dang loc theo
            # ten mien, khong phai link chet. Danh dau de chan doan ra ma
            # MANG_CUA_BAN_CHAN thay vi KET_NOI_TU_CHOI.
            if (res.status == "PAGE_ERROR" and vadns is not None
                    and vadns.bi_bat_coc(dom)):
                page["mang_chan"] = True

            # Het luot thu bang httpx ma van loi ket noi: Chromium van con co
            # hoi, vi nhieu may chu chi tu choi client khong phai trinh duyet.
            # Chi ap cho loi KHONG co ma HTTP. Trang da tra ma HTTP thi nhanh
            # http_code o tren da quyet roi; lot xuong day thi moi trang 404
            # deu bi mo Chromium, va Chromium doc trang loi 404 xong lai xoa mat
            # ma HTTP_404 - do that ngay 2026-09-06: 29 dong 404, 13 dong thanh
            # TRANG_RONG (phai check tay), khong dong nao giu duoc HTTP_404.
            if (res.status == "PAGE_ERROR" and not getattr(res, "_queued_js", False)
                    and (not res.http_code or page.get("vong_lap"))
                    and _nen_render(cfg, dom, use_js, page, loi_ket_noi=True)):
                res._queued_js = True
                js_queue.append((res, tnorm, tdom, tlabel, page))
            await asyncio.sleep(cfg.network["per_domain_delay"])

        # Hoi robots.txt SAU khi da thu tai trang, va bo qua khi trang da chet
        # han: domain khong phan giai duoc thi robots.txt cung khong tai duoc,
        # con 404/410 thi link mat roi, luat robots khong doi duoc ket luan.
        if robots is not None and not _bo_qua_robots(res, page):
            res.robots = await robots.trang_thai(client, res.source_url)

        # Hoi lai dung URL do voi tu cach Googlebot. Tool ket luan theo nhung gi
        # Google nhin thay - xem D.phan_xu(). Dat SAU robots.txt: link da bi
        # robots cam thi Google khong ghe vao, hoi them cung khong doi ket luan.
        if cfg.googlebot.get("check", True):
            ly_do = _bo_qua_googlebot(res, page)
            if ly_do:
                page["gb_bo_qua"] = ly_do
            else:
                delay = cfg.network["per_domain_delay"]
                async with locks[dom]:
                    gb = await _tai_nhu_googlebot(client, res.source_url,
                                                  GOOGLEBOT_UA, tnorm, tdom, tlabel)
                    await asyncio.sleep(delay)
                    # Nguoi xem thay link ma Googlebot (ban dien thoai) thi khong:
                    # hoi them ban may tinh de biet la giau voi Google hay chi la
                    # giao dien dien thoai bo bot phan chua link. Ket luan van la
                    # mat link - Google index theo ban dien thoai - nhung cau giai
                    # thich khac han, va do la cau ben cung cap se hoi lai.
                    if (res.status == "FOUND" and gb.get("html") and not gb.get("found")
                            and 200 <= (gb.get("http") or 0) < 300):
                        pc = await _tai_nhu_googlebot(client, res.source_url,
                                                      GOOGLEBOT_UA_MAY_TINH,
                                                      tnorm, tdom, tlabel)
                        gb["desktop_found"] = bool(pc.get("found"))
                        await asyncio.sleep(delay)
                page["gb"] = gb

    res.elapsed = "%.1f" % (time.monotonic() - t0)
    res._page = page              # finalize can doc lai; recheck_js cung dung
    if not getattr(res, "_queued_js", False):
        finalize(res, page, cfg, use_js)
    if on_progress:
        on_progress(res)
    elif not quiet:
        print("[%-10s] T%s %s" % (res.status, res.tier, res.source_url[:64]),
              file=sys.stderr)
    return res


# Google index theo ban dien thoai (mobile-first), nen hoi bang UA Googlebot
# dien thoai. Ban may tinh chi dung de giai thich khi hai ban lech nhau.
GOOGLEBOT_UA = (
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36 "
    "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
GOOGLEBOT_UA_MAY_TINH = ("Mozilla/5.0 (compatible; Googlebot/2.1; "
                         "+http://www.google.com/bot.html)")


def _bo_qua_googlebot(res, page):
    """Ly do KHONG hoi Googlebot cho dong nay; chuoi rong = can hoi."""
    if getattr(res, "robots", "") == "bi chan":
        return "robots.txt da cam Google"
    if page.get("mang_chan"):
        return "mang may chay tool chan ten mien nay"
    # Khong co HTTP nao tra ve (DNS hong, timeout, tu choi ket noi): loi nam o
    # tang mang, doi User-Agent khong doi duoc gi. Rieng vong lap chuyen huong
    # thi co the chi lap voi trinh duyet nen van hoi.
    if not res.http_code and not page.get("vong_lap"):
        return "trang khong phan hoi"
    return ""


async def _tai_nhu_googlebot(client, url, ua, tn, td, tl):
    """Tai URL voi User-Agent Googlebot, doc trang y het luot 1.

    Tra ve dict: http, final_url, html, found, rel, indexable, note, points_to,
    anchor_text, khop_tang, sig (tin hieu tho cua trang) - hoac {"loi": ...}.
    KHONG dung toi doi tuong Result cua dong dang check.
    """
    try:
        r = await client.get(url, follow_redirects=True, headers={"User-Agent": ua})
    except httpx.TooManyRedirects:
        return {"loi": "chuyen huong vong tron"}
    except httpx.TimeoutException:
        return {"loi": "timeout"}
    except Exception as e:
        return {"loi": type(e).__name__}
    gb = {"http": r.status_code, "final_url": str(r.url)}
    ctype = r.headers.get("content-type", "").lower()
    gb["html"] = "html" in ctype or "xml" in ctype
    sig = {}
    if gb["html"] and 200 <= r.status_code < 300:
        tam = Result(source_url=url)
        ok, sig = analyse(r.text, gb["final_url"], tam, tn, td, tl,
                          x_robots=r.headers.get_list("x-robots-tag"))
        gb.update(found=ok, rel=tam.rel, indexable=tam.indexable, note=tam.note,
                  points_to=tam.points_to, anchor_text=tam.anchor_text,
                  khop_tang=tam.khop_tang)
    elif gb["html"]:
        sig = {"snippet": r.text[:1500]}
    _redirect_flags(url, gb["final_url"], sig)
    gb["sig"] = sig
    return gb


# Nhung truong mo ta "link nam dau, ra sao". Ket luan theo Googlebot se ghi de
# chung bang nhung gi Googlebot thay, nen phai chup lai goc nhin nguoi xem o lan
# finalize dau tien - finalize duoc goi lai (nhanh.py) ma khong lech ket qua.
TRUONG_GOC_NHIN = ("status", "points_to", "anchor_text", "rel", "indexable",
                   "khop_tang", "note")


def finalize(res, page, cfg, use_js):
    """Chan doan mot dong. Goi lai bao nhieu lan cung ra dung mot ket qua."""
    res._page, res._use_js = page, use_js
    goc = page.setdefault("_nguoi_xem", {k: getattr(res, k) for k in TRUONG_GOC_NHIN})
    for k, v in goc.items():
        setattr(res, k, v)

    forced = cfg.force_js_domain(U.domain_of(res.source_url)) and not use_js
    kq = D.phan_xu(res, page, cfg_js_forced=forced,
                   outbound_limit=int(cfg.raw.get("thresholds", {})
                                      .get("outbound_link_limit", 150)),
                   loose=cfg.loose)
    if kq["view"] == "google":
        # Ket luan dua tren trang Googlebot nhan duoc -> cac cot mo ta link cung
        # phai la cua trang do, khong thi dong ghi "Link con" ma cot Tro ve rong.
        gb = page["gb"]
        for k in ("points_to", "anchor_text", "rel", "indexable", "khop_tang"):
            setattr(res, k, gb.get(k, ""))
        res.status = "FOUND"
        res.note = "; ".join(x for x in (
            gb.get("note"),
            "" if goc["status"] == "FOUND" else "link chi doc duoc qua Googlebot")
            if x)

    code = kq["code"]
    sev, why, todo = D.CATALOG[code]
    sev = D.bump_by_tier(sev, res.tier,
                         {n: t.priority for n, t in cfg.tiers.items()}, code)
    res.ket_luan, res.cach_xu_ly, res.huong_dan_check = D.verdict_of(code)
    sev = D.cap_theo_ket_luan(sev, res.ket_luan)
    res.diag_code = code
    res.severity = str(sev)
    res.muc_do = D.SEV_LABEL[sev]
    if cfg.loose and code == "OK":
        # Cau goc noi "dofollow" - che do long khong xet nofollow nen khong
        # khang dinh duoc dieu do.
        why = "Link song, tro dung URL dich (che do loose: khong xet nofollow / noindex)."
    res.chan_doan = why
    res.viec_can_lam = todo
    them = kq["them"] + D.secondary(res, kq["sig"], code, cfg.loose)
    res.canh_bao_them = ", ".join(dict.fromkeys(c for c in them if c != code))
    res.nguoi_xem = kq["nguoi_xem"]
    res.googlebot = kq["googlebot"] if cfg.googlebot.get("check", True) else ""
    res.yeu_cau = D.yeu_cau(code, res.ket_luan)
    res.vi_tri_link = (kq["sig"] or {}).get("vi_tri", "") if res.status == "FOUND" else ""


TAI_NGUYEN_BO_QUA = ("image", "media", "font")

# Duoi nguong nay coi nhu trang chua ra noi dung. Trung voi nguong TRANG_RONG
# trong diagnose.py - de hai cho lech nhau thi tool cho them mot nhip vo ich.
NGUONG_TRANG_RONG = 400


async def _text_len(page_obj):
    """So ky tu nhin thay tren trang. Loi thi tra 0 de ben goi cho them mot nhip."""
    try:
        return int(await page_obj.evaluate(
            "() => document.body ? document.body.innerText.length : 0"))
    except Exception:
        return 0


async def _chan_tai_nguyen_nang(route):
    # Bo try/except thi moi lan vut tab giua chung se in mot dong loi Playwright
    # cho tung request dang bay - nhieu tab thi thanh mot bai rac tren stderr.
    try:
        if route.request.resource_type in TAI_NGUYEN_BO_QUA:
            await route.abort()
        else:
            await route.continue_()
    except Exception:
        pass


def _xen_ke_domain(queue):
    """Rai deu cac URL cung mot domain ra khap hang doi render.

    Luot render co domain lock nen nhieu URL cung domain phai xep hang. Cach
    chia phai dat DONG THOI hai muc tieu:
      - hai muc lien tiep khac domain, de cac worker khong cung ket o mot lock;
      - domain lon duoc rai deu tu dau den cuoi hang doi.

    Kieu vong tron (moi vong lay mot muc cua moi domain) chi dat muc tieu dau.
    No lam can domain nho truoc roi don toan bo phan con lai cua domain lon vao
    DUOI hang doi - dung cho tat ca worker cung ket vao nhau. Do that tren
    tier 1: 12 muc cuoi cung gan nhu chi con network-316491.mn.co va
    jasa-seo.mn.co, hai domain nay giu 61 link.

    Nen dung vi tri tuong doi: muc thu i trong nhom n muc nam o (i+0.5)/n tren
    truc 0..1. Nhom 31 muc trai deu ca hang doi, nhom 1 muc nam chinh giua.
    Thu tu hang doi khong anh huong ket qua - ket qua duoc ghi nguoc ve dung
    doi tuong Result cua no.
    """
    nhom = defaultdict(list)
    for muc in queue:
        nhom[U.domain_of(muc[0].source_url)].append(muc)
    xep = []
    for dom, ds in nhom.items():
        n = len(ds)
        for i, muc in enumerate(ds):
            xep.append(((i + 0.5) / n, dom, i, muc))
    xep.sort(key=lambda x: (x[0], x[1], x[2]))
    return [x[3] for x in xep]


def _tran_render(cfg) -> float:
    """Tran cung cho MOT lan render, tinh bang giay.

    page.goto() co tham so timeout, nhung page.content() va page.evaluate()
    thi KHONG - API Playwright khong nhan timeout cho hai ham nay, chung cho
    vo han. Mot trang co JS chay lien tuc (mn.co, penzu - dung nhung site
    CLAUDE.md da ghi la "khong bao gio idle") du suc treo o do mai mai.

    Worker dang treo lai dang GIU domain lock, nen cac worker khac boc phai
    URL cung domain se ket theo. Day la cai phanh cuoi cung: qua nguong thi
    vut tab, ghi nhan render that bai, di tiep.
    """
    return (int(cfg.js.get("timeout", 40000))
            + 2 * int(cfg.js.get("wait_after", 0) or 0) + 20000) / 1000.0


async def _tab_moi(ctx, page_obj):
    """Vut tab hong, mo tab moi.

    close() cung phai co tran: tab vua bi huy giua chung con request dang treo,
    co truong hop close() khong bao gio tra ve.
    """
    try:
        await asyncio.wait_for(page_obj.close(), 10)
    except Exception:
        pass
    return await asyncio.wait_for(ctx.new_page(), 60)


async def _doc_trang(page_obj, res, tn, td, tl, page, wait_after, timeout,
                     wait_until):
    """Mo mot URL bang Chromium va doc noi dung that. Ben goi boc trong tran."""
    resp = await page_obj.goto(res.source_url, wait_until=wait_until, timeout=timeout)
    # Cho them mot nhip cho JS kip ve noi dung. Nhieu nen tang (penzu, notion,
    # mn.co) tra ve khung rong o thoi diem DOM san sang.
    if wait_after:
        await page_obj.wait_for_timeout(wait_after)
    # Evernote, Notion co khi den luc nay van con trang tron. Doc ngay thi tool
    # ket luan TRANG_RONG cho mot trang thuc ra la tuong dang nhap. Cho them
    # mot nhip nua roi doc lai - chi ton them thoi gian voi dung trang cham.
    if wait_after and await _text_len(page_obj) < NGUONG_TRANG_RONG:
        await page_obj.wait_for_timeout(wait_after)
    res.rendered = "playwright"
    res.final_url = str(page_obj.url)
    if resp is not None and resp.status in (404, 410):
        # Trinh duyet that cung nhan 404/410: trang chet that, giu nguyen ma
        # HTTP thay vi doc trang bao loi roi ket luan "khong thay link".
        res.status, res.http_code = "PAGE_ERROR", str(resp.status)
        res.note = "HTTP %s" % resp.status
        page.pop("error", None)
        return
    page.pop("error", None)
    page.pop("bi_chan", None)
    _redirect_flags(res.source_url, res.final_url, page)
    xr = (resp.headers.get("x-robots-tag") or "") if resp is not None else ""
    ok, page2 = analyse(await page_obj.content(), res.final_url, res, tn, td, tl,
                        x_robots=[v for v in xr.split("\n") if v.strip()])
    page.update(page2)
    if not ok:
        res.status = "NOT_FOUND"


async def _render_worker(ctx, hang, locks, cfg, use_js, on_js_progress, quiet):
    """Mot tab Chromium, boc viec tu hang doi chung cho den khi het.

    Moi worker giu tab rieng trong context rieng: cookie/session cua site nay
    khong lan sang site kia. Tab chet chi anh huong dung worker do.
    """
    wait_after = int(cfg.js.get("wait_after", 0) or 0)
    timeout = int(cfg.js.get("timeout", 40000))
    delay = float(cfg.network["per_domain_delay"])
    wait_until = cfg.js.get("wait_until", "domcontentloaded")
    tran = _tran_render(cfg)
    page_obj = await asyncio.wait_for(ctx.new_page(), 60)
    try:
        while True:
            try:
                res, tn, td, tl, page = hang.get_nowait()
            except asyncio.QueueEmpty:
                return
            # Cung domain thi van phai xep hang va gian nhip y het luot 1.
            # Thieu doan nay, 4 tab ban cung luc vao mot directory se an HTTP_429
            # gia - dung thu tool duoc lam ra de tranh.
            async with locks[U.domain_of(res.source_url)]:
                try:
                    # wait_for la BAT BUOC, khong phai cho chac an: page.content()
                    # va page.evaluate() khong nhan timeout, chung cho vo han.
                    # Worker treo o day van dang giu domain lock, keo theo moi
                    # worker khac boc phai URL cung domain - ca luot render dung
                    # hinh. Xem _tran_render().
                    await asyncio.wait_for(
                        _doc_trang(page_obj, res, tn, td, tl, page, wait_after,
                                   timeout, wait_until), tran)
                except Exception as e:
                    page["error"] = "js %s: %s" % (type(e).__name__, e)[:200]
                    page["render_that_bai"] = True
                    res.note = ((res.note + "; " if res.note else "")
                                + "js:%s" % type(e).__name__)
                    # Tab vua timeout van con request nen dang treo; de nguyen thi
                    # no keo hong ca nhung URL phia sau. Vut tab do di, mo tab moi.
                    page_obj = await _tab_moi(ctx, page_obj)
                await asyncio.sleep(delay)
            finalize(res, page, cfg, use_js)
            if on_js_progress:
                on_js_progress(res)
            elif not quiet:
                print("[JS %-10s] %s" % (res.status, res.source_url[:60]),
                      file=sys.stderr)
    finally:
        # Tran o day cung bat buoc: tab dang hong thi close() co the khong bao
        # gio tra ve, va gather() se treo dung nhu loi vua sua.
        try:
            await asyncio.wait_for(page_obj.close(), 10)
        except Exception:
            pass


def _bo_render_thua(queue, cfg, use_js):
    """Tach khoi hang doi nhung link ma render KHONG the doi duoc ket luan.

    robots.txt da duoc doc xong tu luot 1, va diagnose() chot
    ROBOTS_CHAN_GOOGLE TRUOC moi nhanh khac (xem diagnose.py, khoi
    'robots.txt cam'). Nghia la voi nhung dong nay, doc duoc noi dung hay
    khong cung ra dung mot ket luan - mo Chromium chi de vut ket qua di.

    Do that tren du an huthamcautienphat ngay 2026-09-06: tier 1 co 324 dong
    robots = "bi chan", 293 dong trong so do da tra gia mo trinh duyet, va
    ca 324 deu ra ROBOTS_CHAN_GOOGLE - khong mot dong nao doi ket luan nho
    render. Bo han khoang nay cat ~15 phut khoi tier 1.

    Tra ve (hang doi con lai, so dong da chot ngay).
    """
    con, chot = [], []
    for muc in queue:
        if getattr(muc[0], "robots", "") == "bi chan":
            chot.append(muc)
        else:
            con.append(muc)
    for res, tn, td, tl, page in chot:
        finalize(res, page, cfg, use_js)
    return con, len(chot)


async def recheck_js(queue, cfg, use_js, on_js_progress=None, quiet=False,
                     locks=None, vadns=None):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        if not quiet:
            print("Chua cai playwright -> bo qua buoc render JS. "
                  "Chay: pip install playwright && playwright install chromium",
                  file=sys.stderr)
        # Khong render duoc thi KHONG duoc ket luan la mat link: danh dau lai de
        # module chan doan tra ve CAN_BAT_JS thay vi LINK_BI_GO.
        for res, tn, td, tl, page in queue:
            page["js_unavailable"] = True
            finalize(res, page, cfg, use_js)
        return False

    so_tab = max(1, min(cfg.js_concurrency(), len(queue)))
    if locks is None:
        locks = defaultdict(asyncio.Lock)
    if not quiet:
        print("\nRender lai %d URL bang Chromium (%d tab song song)..."
              % (len(queue), so_tab), file=sys.stderr)

    hang = asyncio.Queue()
    for muc in _xen_ke_domain(queue):
        hang.put_nowait(muc)

    async with async_playwright() as pw:
        # Chromium la tien trinh rieng, khong dung socket cua Python, nen
        # bang IP da va phai truyen rieng cho no.
        args = []
        rule = vadns.host_resolver_rules() if vadns is not None else None
        if rule:
            args.append(rule)
        b = await pw.chromium.launch(args=args)
        try:
            ctxs = []
            for _ in range(so_tab):
                ctx = await asyncio.wait_for(
                    b.new_context(user_agent=cfg.network["user_agent"]), 60)
                # Anh, video, font khong bao gio chua the <a>. Chan lai giup
                # trang nang (Notion, Evernote) mo nhanh hon han, va giu RAM moi
                # tab o muc chap nhan duoc khi chay nhieu tab cung luc.
                await ctx.route("**/*", _chan_tai_nguyen_nang)
                ctxs.append(ctx)
            # return_exceptions: mot worker chet khong duoc keo sap ca luot
            # render. Nhung dong con lai trong hang se roi vao luoi an toan
            # cuoi run_check va duoc finalize theo du lieu luot 1.
            loi = await asyncio.gather(
                *[_render_worker(c, hang, locks, cfg, use_js, on_js_progress,
                                 quiet) for c in ctxs],
                return_exceptions=True)
            for e in loi:
                if isinstance(e, BaseException):
                    print("CANH BAO: mot tab render dung giua chung: %s: %s"
                          % (type(e).__name__, e), file=sys.stderr)
        finally:
            # Ket qua da tinh xong het o tren; dung de trinh duyet wedge lam
            # treo ngay truoc buoc ghi file.
            try:
                await asyncio.wait_for(b.close(), 30)
            except Exception:
                pass
    return True


async def run_check(cfg, rows, targets, use_js, on_progress=None,
                    on_js_start=None, on_js_progress=None, quiet=False):
    """Chay check cho mot danh sach dong. Tra ve list Result da chan doan xong.

    on_progress(res)    goi sau moi link kiem tra xong
    on_js_start(n)      goi truoc khi bat dau render lai n URL bang Chromium
    on_js_progress(res) goi sau moi URL render xong
    """
    sem = asyncio.Semaphore(int(cfg.network["concurrency"]))
    locks, jsq = defaultdict(asyncio.Lock), []
    # Mot bo nho dung chung cho ca dot chay: moi host tai robots.txt dung 1 lan.
    robots = (robotscheck.BoNhoRobots(float(cfg.robots.get("timeout", 10)))
              if cfg.robots.get("check", True) else None)
    vadns = dnsfix.VaDNS(bool(cfg.network.get("dns_fallback", True)))
    limits = httpx.Limits(max_connections=int(cfg.network["concurrency"]) * 2)
    async with httpx.AsyncClient(headers={"User-Agent": cfg.network["user_agent"]},
                                 timeout=float(cfg.network["timeout"]),
                                 verify=bool(cfg.network["verify_ssl"]),
                                 limits=limits) as c:
        results = await asyncio.gather(*[
            check_one(c, r, sem, locks, targets, jsq, cfg, use_js, on_progress,
                      quiet, robots, vadns)
            for r in rows])
    vadns.in_bao_cao(quiet)
    run_check.dns_va = vadns.tom_tat()

    js_ok = True
    # Loc TRUOC khi bao on_js_start, de tong tren thanh tien trinh la so lan
    # render that su phai chay.
    jsq, bo_qua = _bo_render_thua(jsq, cfg, use_js)
    run_check.js_skipped_robots = bo_qua
    if bo_qua and not quiet:
        print("Bo qua %d lan render: robots.txt cua site da cam Googlebot, "
              "ket luan khong doi duoc." % bo_qua, file=sys.stderr)
    if jsq:
        if on_js_start:
            on_js_start(len(jsq))
        js_ok = await recheck_js(jsq, cfg, use_js, on_js_progress, quiet, locks,
                                 vadns)
    run_check.js_available = js_ok
    for r in results:
        if not r.diag_code:
            finalize(r, getattr(r, "_page", {}), cfg, use_js)
    # Tra socket ve nguyen trang: tien trinh nay con chay tiep cac buoc khac
    # (doi soat, ghi chu) va khong duoc mang theo anh xa DNS cua dot check.
    vadns.go_patch()
    return list(results)


def build_targets(rows, cfg):
    """Dung tap URL dich cho tung tier.

    Moi tier khai mot hoac nhieu dich (xem Tier.targets):
        ("money", None)  -> cac URL dich cua money site
        ("tier", N)      -> toan bo source_url cua tier N trong master CSV

    Tra ve {tier: (norms, doms)} voi norms/doms la dict anh xa sang TEN TANG
    ("money", "tier 2"...) de con ghi duoc vao cot khop_tang. Dich khai truoc
    thang khi mot URL thuoc nhieu tap cung luc."""
    by_tier = defaultdict(list)
    for r in rows:
        by_tier[str(r["tier"])].append(r["source_url"])

    targets = {}
    for n, t in cfg.tiers.items():
        norms, doms = {}, {}
        for kind, num in t.targets:
            if kind == "money":
                label = "money"
                urls = cfg.target_urls
                extra_doms = {cfg.money_domain} | set(cfg.extra_domains)
            else:
                label = "tier %s" % num
                urls = by_tier.get(str(num), [])
                extra_doms = {U.domain_of(u) for u in urls}
            for u in urls:
                norms.setdefault(U.normalize(u), label)
            for d in extra_doms:
                if d:
                    doms.setdefault(d, label)
        primary = t.targets[0]
        label = "money" if primary[0] == "money" else "tier %s" % primary[1]
        targets[str(n)] = (norms, doms, label)
    return targets


def load_master(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r.get("source_url")]


def write_csv(results, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cols = [f.name for f in fields(Result)]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in results:
            w.writerow({k: v for k, v in asdict(r).items() if k in cols})
    return path


def summary(results, cfg):
    out = []
    stats = defaultdict(lambda: defaultdict(int))
    for r in results:
        stats[r.tier][r.status] += 1
    out.append("=" * 62)
    for t in sorted(stats, key=lambda x: int(x) if str(x).isdigit() else 99):
        s = stats[t]
        tot = sum(s.values())
        # Dem theo cot status = trinh duyet co thay the <a> hay khong. KHONG phai
        # ket luan: link nguoi xem thay van co the mat vi Google khong thay.
        out.append("Tier %s: %5d link | thay the <a> %5d | khong thay %5d | loi trang %5d"
                   % (t, tot, s["FOUND"], s["NOT_FOUND"], s["PAGE_ERROR"]))

    # ------------------------------------------------- chot lai cho nguoi dung
    d = D.dem_ket_luan(results)
    tong = d["TONG"] or 1
    pc = lambda n: 100.0 * n / tong
    out.append("-" * 62)
    out.append("CHOT LAI")
    out.append("  Link con      : %5d (%4.1f%%)  - trong do %d link hoan hao"
               % (d[D.V_SONG], pc(d[D.V_SONG]), d["HOAN_HAO"]))
    out.append("  Link mat      : %5d (%4.1f%%)  - ke ca trang noindex, thay nguon moi"
               % (d[D.V_MAT], pc(d[D.V_MAT])))
    out.append("  Phai check tay: %5d (%4.1f%%)  - tool chua doc duoc, CHUA ket luan"
               % (d[D.V_CHECK], pc(d[D.V_CHECK])))
    if d[D.V_CHECK]:
        out.append("      %-16s %4d  (may lam)" % (D.X_TOOL, d[D.X_TOOL]))
        out.append("      %-16s %4d  (nguoi lam)" % (D.X_NGUOI, d[D.X_NGUOI]))
        out.append("      Danh sach cu the: sheet 'Can check tay' trong file xlsx")

    by_sev = defaultdict(int)
    for r in results:
        by_sev[r.muc_do] += 1
    out.append("-" * 62)
    for lab in ("CHET", "NANG", "CANH BAO", "GHI CHU", "TOT"):
        if by_sev[lab]:
            out.append("  %-9s : %d" % (lab, by_sev[lab]))

    top = defaultdict(int)
    for r in results:
        if r.diag_code and r.diag_code != "OK":
            top[r.diag_code] += 1
    if top:
        out.append("-" * 62)
        out.append("Loi hay gap nhat:")
        for k, v in sorted(top.items(), key=lambda kv: -kv[1])[:10]:
            out.append("  %-26s %4d  %s" % (k, v, D.CATALOG[k][1][:60]))
    return "\n".join(out)


async def main():
    ap = argparse.ArgumentParser(description="Kiem tra backlink theo config YAML")
    ap.add_argument("-c", "--config", required=True)
    ap.add_argument("--tier", help="chi check mot tang, vd --tier 1")
    ap.add_argument("--all", action="store_true", help="check toan bo cac tang")
    ap.add_argument("--limit", type=int, help="chi check N dong dau (de test)")
    ap.add_argument("--js", action="store_true", help="ep render JS cho moi link khong thay")
    ap.add_argument("--no-js", action="store_true", help="tat render JS du config bat")
    ap.add_argument("-i", "--input", help="ghi de master CSV trong config")
    ap.add_argument("-o", "--output", help="ghi de duong dan file ket qua (khong duoi)")
    args = ap.parse_args()

    cfg = bl_config.load(args.config)
    if not args.tier and not args.all:
        ap.error("phai chon --tier N hoac --all")

    master = args.input or cfg.master_csv
    if not Path(master).exists():
        raise SystemExit("Chua co %s. Chay 'python src/ingest.py -c %s' truoc."
                         % (master, args.config))
    all_rows = load_master(master)
    targets = build_targets(all_rows, cfg)

    rows = all_rows
    if args.tier:
        rows = [r for r in rows if str(r["tier"]) == str(args.tier)]
        if not rows:
            raise SystemExit("Khong co dong nao thuoc tier %s trong %s" % (args.tier, master))
    if args.limit:
        rows = rows[:args.limit]

    use_js = cfg.js_for_tier(args.tier or 0, args.js) if args.tier else args.js
    if args.no_js:
        use_js = False

    print("Site      : %s (%s)" % (cfg.site_name, cfg.money_domain), file=sys.stderr)
    print("Se check  : %d/%d link | JS: %s | concurrency %s | delay %ss"
          % (len(rows), len(all_rows), "bat" if use_js else "tat",
             cfg.network["concurrency"], cfg.network["per_domain_delay"]),
          file=sys.stderr)
    print("", file=sys.stderr)

    results = await run_check(cfg, rows, targets, use_js)
    import nhanh
    nhanh.danh_dau(results, cfg, nhanh.ban_do(cfg, {"dot nay": results}), finalize)

    today = date.today().isoformat()
    tier_label = args.tier if args.tier else "all"
    if args.output:
        base = Path(args.output)
        csv_path = base.with_suffix(".csv")
        xlsx_path = base.with_suffix(".xlsx")
    else:
        csv_path = cfg.out_path(today, tier_label, "csv")
        xlsx_path = cfg.out_path(today, tier_label, "xlsx")

    formats = [f.lower() for f in cfg.output["formats"]]
    if "csv" in formats:
        write_csv(results, csv_path)
        print("\nDa luu CSV : %s" % csv_path, file=sys.stderr)
    if "xlsx" in formats:
        try:
            import report
            report.write_xlsx(results, xlsx_path, cfg)
            print("Da luu XLSX: %s  (da to mau theo muc do)" % xlsx_path, file=sys.stderr)
        except ImportError:
            print("Chua cai openpyxl -> bo qua XLSX. Chay: pip install openpyxl",
                  file=sys.stderr)

    print("\n" + summary(results, cfg), file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
