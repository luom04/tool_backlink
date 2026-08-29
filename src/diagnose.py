"""
Chuan doan loi cho tung backlink.

Checker chi thu thap tin hieu tho (ma HTTP, ten exception, tieu de trang,
the meta, thuoc tinh cua the <a>...). Module nay bien tin hieu do thanh mot
ma loi ngan gon + cau giai thich tieng Viet + viec can lam.

Muc nghiem trong (severity), dung de to mau trong file XLSX:
    1 CHET      do dam   - link mat han, phai thay nguon moi
    2 NANG      do cam   - link con nhung dang hong, phai xu ly som
    3 CANH BAO  vang     - link con, gia tri thap hon ky vong
    4 GHI CHU   xanh nhat- khong sai, chi de biet
    5 TOT       xanh la  - khong can lam gi
"""

import re

SEV_CHET, SEV_NANG, SEV_CANHBAO, SEV_GHICHU, SEV_TOT = 1, 2, 3, 4, 5

SEV_LABEL = {1: "CHET", 2: "NANG", 3: "CANH BAO", 4: "GHI CHU", 5: "TOT"}

SOFT_404_PAT = re.compile(
    r"(404|not\s*found|page\s+not\s+found|trang\s+kh(o|ô)ng\s+t(o|ồ)n\s+t(a|ạ)i|"
    r"n(o|ộ)i\s*dung\s+(da|đã)\s+b(i|ị)\s+x(o|ó)a|no\s+longer\s+available|"
    r"da\s+b(i|ị)\s+g(o|ỡ)|deleted|removed by)", re.I)

PARKED_PAT = re.compile(
    r"(domain\s+(is\s+)?for\s+sale|buy\s+this\s+domain|t(e|ê)n\s+mi(e|ề)n\s+n(a|à)y\s+"
    r"(dang\s+)?(duoc\s+)?rao\s+b(a|á)n|parked\s+(free|domain)|expired\s+domain|"
    r"this\s+domain\s+(has\s+)?expired|godaddy.*parking)", re.I)

LOGIN_PAT = re.compile(
    r"(dang\s*nh(a|ậ)p\s+(de|để)\s+(xem|ti(e|ế)p)|(please\s+)?(log|sign)\s*in\s+to\s+"
    r"(view|continue|see)|members\s+only|c(a|ầ)n\s+(dang\s*nh(a|ậ)p|tai\s+kho(a|ả)n))",
    re.I)

CAPTCHA_PAT = re.compile(
    r"(cloudflare|just a moment|checking your browser|captcha|are you (a )?human|"
    r"ddos.?guard|attention required|access denied|akamai|请稍候)", re.I)

# Rut gon link / trang trung gian. Tach lam hai:
#   HOST    - so khop dung ten mien (khong dung chuoi con, vi "t.co" nam ngay
#             trong "huthamcautienphat.com" -> se bao nham hang loat)
#   PATTERN - so khop trong duong dan + tham so cua href
SHORTENER_HOSTS = (
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "cutt.ly",
    "shorturl.at", "rebrand.ly", "s.id", "l.facebook.com", "out.reddit.com",
    "href.li", "lnkd.in", "buff.ly", "db.tt", "qr.ae", "adf.ly",
)
REDIRECT_PATTERNS = (
    "/redirect?", "/goto/", "?url=", "&url=", "/away?", "/link?url=",
    "/url?q=", "?redirect=", "&redirect=", "/out?", "/r.php?",
)

# giu ten cu de code khac khong vo
SHORTENER = SHORTENER_HOSTS + REDIRECT_PATTERNS


def via_redirect(raw_href: str, abs_href: str) -> bool:
    """Link co di qua trang rut gon / chuyen huong trung gian khong."""
    from urllib.parse import urlparse
    host = (urlparse(abs_href or raw_href or "").netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if any(host == h or host.endswith("." + h) for h in SHORTENER_HOSTS):
        return True
    low = (raw_href or "").lower()
    return any(p in low for p in REDIRECT_PATTERNS)


NOFOLLOW_REL = ("nofollow", "ugc", "sponsored")

# ma loi -> (muc nghiem trong, giai thich, viec can lam)
CATALOG = {
    # ---- trang chet han
    "DOMAIN_KHONG_PHAN_GIAI": (SEV_CHET,
        "Ten mien khong phan giai duoc (DNS that bai) - rat co the domain da het han.",
        "Bo link nay khoi danh sach, tim nguon thay the."),
    "KET_NOI_TU_CHOI": (SEV_CHET,
        "May chu tu choi ket noi hoac khong con phuc vu.",
        "Kiem tra lai bang trinh duyet 1 lan; neu van hong thi thay nguon moi."),
    "SSL_LOI": (SEV_NANG,
        "Chung chi HTTPS het han hoac khong hop le.",
        "Trang van co the con song. Mo bang trinh duyet de xac nhan truoc khi bo."),
    "TIMEOUT": (SEV_NANG,
        "Trang khong phan hoi trong thoi gian cho.",
        "Chay lai rieng link nay voi timeout cao hon truoc khi ket luan."),
    "HTTP_404": (SEV_CHET,
        "Trang tra ve 404 - bai dang da bi xoa han.",
        "Dang lai bai moi tren cung site, hoac thay bang nguon khac."),
    "HTTP_410": (SEV_CHET,
        "Trang tra ve 410 Gone - chu site chu dong xoa vinh vien.",
        "Khong dang lai duoc tren URL cu. Tim nguon khac."),
    "HTTP_403_CHAN_BOT": (SEV_CANHBAO,
        "Bi chan 403 - thuong la tuong lua Cloudflare chan bot chu khong phai mat link.",
        "Bat --js hoac mo tay de xac nhan. Dung voi ket luan la mat link."),
    "HTTP_401": (SEV_CANHBAO,
        "Trang doi dang nhap moi cho xem.",
        "Kiem tra tay bang tai khoan da dung de dang bai."),
    "HTTP_429": (SEV_CANHBAO,
        "Bi gioi han tan suat (429) - ta ban qua nhanh vao domain nay.",
        "Tang per_domain_delay, giam concurrency roi chay lai rieng domain nay."),
    "HTTP_5XX": (SEV_NANG,
        "May chu nguon dang loi (5xx). Thuong la tam thoi.",
        "Chay lai sau vai gio truoc khi ket luan."),
    "KHONG_PHAI_HTML": (SEV_NANG,
        "URL tra ve file khong phai HTML (PDF, anh, JSON...).",
        "Kiem tra lai URL trong file nguon, co the bi dan nham."),
    "SOFT_404": (SEV_CHET,
        "Tra ve 200 nhung noi dung la trang bao loi / bai da bi xoa.",
        "Coi nhu mat link. Dang lai hoac thay nguon."),
    "DOMAIN_RAO_BAN": (SEV_CHET,
        "Domain da het han va dang do trang rao ban / parking.",
        "Bo khoi danh sach. Link nay khong con gia tri va co the doc hai."),
    "CHUYEN_VE_TRANG_CHU": (SEV_CHET,
        "Bi chuyen huong ve trang chu - dau hieu bai viet da bi go.",
        "Dang lai bai. Neu site khong con cho dang, thay nguon."),
    "CHUYEN_SANG_DOMAIN_KHAC": (SEV_NANG,
        "Bi chuyen sang mot ten mien hoan toan khac - site co the da doi chu.",
        "Kiem tra tay xem noi dung con khong."),

    # ---- trang song nhung khong thay link
    "LINK_BI_GO": (SEV_NANG,
        "Trang con song, doc duoc noi dung that, nhung khong con the <a> nao "
        "tro ve he thong cua minh.",
        "Admin da go link hoac xoa noi dung trong profile. Dang lai hoac thay nguon."),
    "CHUA_RENDER_DUOC": (SEV_CANHBAO,
        "Da mo bang Chromium nhung van khong tai duoc noi dung that "
        "(trang treo, chan bot tan goc, hoac qua cham).",
        "Mo tay bang trinh duyet. KHONG tinh la mat link."),
    "CHUA_CAI_PLAYWRIGHT": (SEV_CANHBAO,
        "Tier nay can render JavaScript nhung may chua cai Playwright nen chua "
        "doc duoc noi dung that. KHONG phai ket luan mat link.",
        "Chay: pip install playwright && playwright install chromium, roi chay lai tier nay."),
    "CAN_BAT_JS": (SEV_CANHBAO,
        "Domain nay render noi dung bang JavaScript, ban chua bat --js.",
        "Chay lai tier nay voi co --js truoc khi ket luan mat link."),
    "TUONG_DANG_NHAP": (SEV_CANHBAO,
        "Noi dung bi che sau tuong dang nhap nen khong doc duoc link.",
        "Kiem tra tay bang tai khoan da dung de dang."),
    "BI_CHAN_CAPTCHA": (SEV_CANHBAO,
        "Trang tra ve man hinh chong bot (Cloudflare / captcha).",
        "Bat --js, hoac kiem tra tay. Khong tinh la mat link."),
    "TRANG_RONG": (SEV_NANG,
        "Trang tai duoc nhung gan nhu khong co noi dung.",
        "Kiem tra tay - co the bai bi go noi dung nhung URL van song."),

    # ---- link con, nhung chat luong co van de
    "OK": (SEV_TOT,
        "Link song, dofollow, tro dung URL dich.",
        "Khong can lam gi."),
    "NOFOLLOW": (SEV_CANHBAO,
        "Link con nhung mang thuoc tinh nofollow/ugc/sponsored - khong truyen suc manh SEO.",
        "Ghi nhan. Chi xu ly khi day la link tier 1 quan trong."),
    "SAI_URL_DICH": (SEV_CANHBAO,
        "Link tro dung ten mien nhung sai trang cu the so voi ke hoach.",
        "Kiem tra tay va sua ve dung URL dich neu con quyen chinh sua."),
    "TRO_SAI_TANG": (SEV_CANHBAO,
        "Link VAN CON va van tro ve he thong cua minh, nhung roi vao tang khac "
        "voi khai bao trong config. Xem cot khop_tang de biet no tro vao dau.",
        "Khong phai link hong - khong dua vao yeu cau bu. Hoac sua lai khai bao "
        "tier trong config cho dung thuc te, hoac dat lai link cho dung tang."),
    "TRANG_NOINDEX": (SEV_NANG,
        "The <a> VAN CON tren trang, nhung trang mang the noindex nen Google "
        "khong tinh link nay.",
        "Link chua mat - khong can mo tay xac minh. Uu tien tim them nguon khac "
        "neu day la tier 1 hoac 2."),
    "CANONICAL_KHAC": (SEV_CANHBAO,
        "Trang co canonical tro sang URL khac, gia tri link bi chuyen di noi khac.",
        "Kiem tra tay xem ban canonical co giu link khong."),
    "ANCHOR_RONG": (SEV_GHICHU,
        "Link ton tai nhung anchor text rong hoac chi la anh.",
        "Khong gap. Neu sua duoc thi dat anchor co tu khoa."),
    "ANCHOR_LA_URL": (SEV_GHICHU,
        "Anchor text la URL tran, gia tri tu khoa gan nhu bang khong.",
        "Khong gap. Sua thanh anchor co nghia neu con quyen chinh sua."),
    "LINK_QUA_TRUNG_GIAN": (SEV_CANHBAO,
        "Link di qua trang chuyen huong / rut gon, khong tro thang ve dich.",
        "Kiem tra xem trung gian co chan bot khong. Uu tien link tro thang."),
    "TRANG_NHIEU_LINK_RA": (SEV_CANHBAO,
        "Trang chua qua nhieu link ra ngoai - dac trung cua trang spam/link farm.",
        "Gia tri truyen ve rat loang. Khong dau tu them vao nguon nay."),
    "KHONG_RO": (SEV_CANHBAO,
        "Khong xac dinh duoc nguyen nhan cu the.",
        "Kiem tra tay."),
}


# =====================================================================
# TANG "KET LUAN" - tra loi cau hoi: link nay co phai mo tay kiem tra khong?
#
# Muc do (1..5) noi ve MUC NGHIEM TRONG. Tang nay noi ve DO TIN CAY cua
# ket luan, la hai chuyen khac nhau:
#
#   SONG       tool doc duoc trang va NHIN THAY the <a>. Chac chan con link.
#              Khong can mo tay. Muc do se noi link do tot hay con khiem khuyet.
#   MAT        tool doc duoc trang va chac chan link khong con (404, 410,
#              domain het han, bai bi go, noindex...). Khong can mo tay,
#              viec can lam la thay nguon moi.
#   CHECK_TAY  tool KHONG doc duoc noi dung that (bi chan bot, captcha, tuong
#              dang nhap, timeout, chua render JS...). Ket luan khong dang tin
#              - dung dem nhung link nay vao so link mat.
#
# CACH_XU_LY cho biet phai lam gi voi nhom CHECK_TAY: co cai chi can chay lai
# tool la xong (may lam), co cai bat buoc mo trinh duyet (nguoi lam).
# =====================================================================

V_SONG, V_MAT, V_CHECK = "SONG", "MAT", "CHECK_TAY"

V_LABEL = {
    V_SONG:  "Link con",
    V_MAT:   "Link mat",
    V_CHECK: "Phai check tay",
}

# Cach xu ly cho nhom CHECK_TAY
X_TOOL, X_NGUOI = "Chay lai tool", "Mo trinh duyet"

VERDICT = {
    # ---------------------------------------------- chac chan con link
    "OK":                   (V_SONG,  ""),
    "NOFOLLOW":             (V_SONG,  ""),
    "ANCHOR_RONG":          (V_SONG,  ""),
    "ANCHOR_LA_URL":        (V_SONG,  ""),
    "SAI_URL_DICH":         (V_SONG,  ""),
    "LINK_QUA_TRUNG_GIAN":  (V_SONG,  ""),
    "TRANG_NHIEU_LINK_RA":  (V_SONG,  ""),
    "CANONICAL_KHAC":       (V_SONG,  ""),
    "TRO_SAI_TANG":         (V_SONG,  ""),
    # Trang noindex van la "link con": tool doc duoc trang va nhin thay the <a>.
    # Muc do NANG da noi len viec no khong truyen gia tri SEO.
    "TRANG_NOINDEX":        (V_SONG,  ""),

    # ---------------------------------------------- chac chan mat link
    "DOMAIN_KHONG_PHAN_GIAI": (V_MAT, ""),
    "HTTP_404":             (V_MAT,   ""),
    "HTTP_410":             (V_MAT,   ""),
    "SOFT_404":             (V_MAT,   ""),
    "DOMAIN_RAO_BAN":       (V_MAT,   ""),
    "CHUYEN_VE_TRANG_CHU":  (V_MAT,   ""),
    "LINK_BI_GO":           (V_MAT,   ""),

    # ---------------------------------------------- chua ket luan duoc
    "CHUA_CAI_PLAYWRIGHT":  (V_CHECK, X_TOOL),
    "CHUA_RENDER_DUOC":     (V_CHECK, X_NGUOI),
    "CAN_BAT_JS":           (V_CHECK, X_TOOL),
    "HTTP_429":             (V_CHECK, X_TOOL),
    "HTTP_5XX":             (V_CHECK, X_TOOL),
    "TIMEOUT":              (V_CHECK, X_TOOL),
    "HTTP_403_CHAN_BOT":    (V_CHECK, X_NGUOI),
    "HTTP_401":             (V_CHECK, X_NGUOI),
    "BI_CHAN_CAPTCHA":      (V_CHECK, X_NGUOI),
    "TUONG_DANG_NHAP":      (V_CHECK, X_NGUOI),
    "SSL_LOI":              (V_CHECK, X_NGUOI),
    "KET_NOI_TU_CHOI":      (V_CHECK, X_NGUOI),
    "CHUYEN_SANG_DOMAIN_KHAC": (V_CHECK, X_NGUOI),
    "KHONG_PHAI_HTML":      (V_CHECK, X_NGUOI),
    "TRANG_RONG":           (V_CHECK, X_NGUOI),
    "KHONG_RO":             (V_CHECK, X_NGUOI),
}

# Cau huong dan ngan gon cho tung ma trong nhom CHECK_TAY. Hien o sheet
# "Can check tay" de nguoi dung khong phai doan phai lam gi.
HUONG_DAN_CHECK = {
    "CHUA_CAI_PLAYWRIGHT": "Cai Playwright roi chay lai tier nay: "
                           "pip install playwright && playwright install chromium",
    "CAN_BAT_JS":          "Chay lai tier nay voi co --js",
    "HTTP_429":            "Tang per_domain_delay, giam concurrency, chay lai rieng domain nay",
    "HTTP_5XX":            "May chu nguon dang loi. Chay lai sau vai gio",
    "TIMEOUT":             "Chay lai voi timeout cao hon. Van timeout thi mo tay",
    "HTTP_403_CHAN_BOT":   "Mo URL bang trinh duyet, Ctrl+F tim ten mien money site",
    "HTTP_401":            "Dang nhap bang tai khoan da dung de dang bai roi tim link",
    "BI_CHAN_CAPTCHA":     "Mo URL bang trinh duyet, qua captcha roi Ctrl+F tim link",
    "TUONG_DANG_NHAP":     "Dang nhap vao site roi kiem tra link con trong bai khong",
    "SSL_LOI":             "Mo bang trinh duyet, bo qua canh bao chung chi de xem trang",
    "KET_NOI_TU_CHOI":     "Mo bang trinh duyet 1 lan. Van hong thi coi nhu mat link",
    "CHUYEN_SANG_DOMAIN_KHAC": "Mo URL cuoi xem noi dung bai cu con khong",
    "KHONG_PHAI_HTML":     "Doi chieu lai URL trong file nguon, co the dan nham",
    "TRANG_RONG":          "Mo URL xem bai con noi dung khong hay chi con vo trang",
    "KHONG_RO":            "Mo URL bang trinh duyet, Ctrl+F tim ten mien money site",
}


def verdict_of(code):
    """code -> (ket_luan, cach_xu_ly, huong_dan). Ma la -> coi nhu phai check tay."""
    v, how = VERDICT.get(code, (V_CHECK, X_NGUOI))
    return v, how, HUONG_DAN_CHECK.get(code, "")


def dem_ket_luan(results):
    """Dem so link theo ket luan. Tra ve dict de dung chung cho console/xlsx."""
    d = {V_SONG: 0, V_MAT: 0, V_CHECK: 0, "TONG": 0, "HOAN_HAO": 0,
         X_TOOL: 0, X_NGUOI: 0}
    for r in results:
        v = getattr(r, "ket_luan", "") or V_CHECK
        d["TONG"] += 1
        d[v] = d.get(v, 0) + 1
        if v == V_SONG and str(getattr(r, "severity", "")) == str(SEV_TOT):
            d["HOAN_HAO"] += 1
        if v == V_CHECK:
            how = getattr(r, "cach_xu_ly", "") or X_NGUOI
            d[how] = d.get(how, 0) + 1
    return d


def diagnose(res, page, cfg_js_forced=False, outbound_limit=150):
    """Tra ve (ma_loi, muc_nghiem_trong, giai_thich, viec_can_lam).

    res  : doi tuong Result da duoc checker dien
    page : dict tin hieu tho tu trang (title, text_len, outbound, html_snippet...)
    """
    page = page or {}
    title = page.get("title", "") or ""
    snippet = page.get("snippet", "") or ""
    blob = (title + " " + snippet)[:6000]
    err = (page.get("error") or "").lower()
    code = 0
    try:
        code = int(res.http_code)
    except (TypeError, ValueError):
        code = 0

    # ---------------------------------------------------------- trang loi
    if res.status == "PAGE_ERROR":
        if "ssl" in err or "certificate" in err:
            key = "SSL_LOI"
        elif "timeout" in err or "timedout" in err:
            key = "TIMEOUT"
        elif "getaddrinfo" in err or "name or service" in err or "nodename" in err \
                or "dns" in err:
            key = "DOMAIN_KHONG_PHAN_GIAI"
        elif "connect" in err or "refused" in err or "reset" in err or "unreachable" in err:
            key = "KET_NOI_TU_CHOI"
        elif code == 404:
            key = "HTTP_404"
        elif code == 410:
            key = "HTTP_410"
        elif code == 403:
            key = "BI_CHAN_CAPTCHA" if CAPTCHA_PAT.search(blob) else "HTTP_403_CHAN_BOT"
        elif code == 401:
            key = "HTTP_401"
        elif code == 429:
            key = "HTTP_429"
        elif 500 <= code <= 599:
            key = "HTTP_5XX"
        elif "html" in err or "content-type" in err or page.get("not_html"):
            key = "KHONG_PHAI_HTML"
        else:
            key = "KHONG_RO"
        return _pack(key, res)

    # ---------------------------------------------------------- trang 200 nhung hong
    if PARKED_PAT.search(blob):
        return _pack("DOMAIN_RAO_BAN", res)
    if SOFT_404_PAT.search(title):
        return _pack("SOFT_404", res)
    if page.get("redirected_off_domain"):
        return _pack("CHUYEN_SANG_DOMAIN_KHAC", res)
    if page.get("redirected_to_home"):
        return _pack("CHUYEN_VE_TRANG_CHU", res)

    # ---------------------------------------------------------- khong thay link
    if res.status == "NOT_FOUND":
        if CAPTCHA_PAT.search(blob):
            return _pack("BI_CHAN_CAPTCHA", res)
        if LOGIN_PAT.search(blob):
            return _pack("TUONG_DANG_NHAP", res)
        if page.get("js_unavailable"):
            return _pack("CHUA_CAI_PLAYWRIGHT", res)
        if page.get("render_that_bai"):
            return _pack("CHUA_RENDER_DUOC", res)
        if cfg_js_forced and res.rendered != "playwright":
            return _pack("CAN_BAT_JS", res)
        if page.get("text_len", 9999) < 400:
            return _pack("TRANG_RONG", res)
        return _pack("LINK_BI_GO", res)

    # ---------------------------------------------------------- link con song
    if res.indexable == "no":
        key = "CANONICAL_KHAC" if "canonical" in (res.note or "").lower() else "TRANG_NOINDEX"
        return _pack(key, res)
    rel = (res.rel or "").lower()
    if any(r in rel for r in NOFOLLOW_REL):
        return _pack("NOFOLLOW", res)
    if page.get("via_redirect"):
        return _pack("LINK_QUA_TRUNG_GIAN", res)
    if "khong khop URL" in (res.note or "") or page.get("domain_only_match"):
        return _pack("SAI_URL_DICH", res)
    # Link con, tro dung he thong cua minh, nhung khong phai tang da khai bao.
    # Day la sai lech giua so do tren giay va thuc te, khong phai link hong.
    if page.get("sai_tang"):
        return _pack("TRO_SAI_TANG", res)
    if page.get("outbound", 0) > outbound_limit:
        return _pack("TRANG_NHIEU_LINK_RA", res)
    a = (res.anchor_text or "").strip()
    if not a or a == "(anh / rong)":
        return _pack("ANCHOR_RONG", res)
    if a.lower().startswith(("http://", "https://", "www.")):
        return _pack("ANCHOR_LA_URL", res)
    return _pack("OK", res)


def _pack(key, res):
    sev, why, todo = CATALOG[key]
    return key, sev, why, todo


def bump_by_tier(sev: int, tier, tier_priority: dict) -> int:
    """Tier cang cao trong kim tu thap thi cung mot loi cang nghiem trong.

    tier_priority: {so_tier: do_uu_tien}. Tier co priority = 1 duoc nang muc len
    mot bac; tier co priority >= 4 duoc ha mot bac (chi theo doi tong quan).
    """
    try:
        p = int(tier_priority.get(int(tier), int(tier)))
    except (TypeError, ValueError):
        return sev
    if sev >= SEV_TOT:
        return sev
    if p <= 1:
        return max(SEV_CHET, sev - 1)
    if p >= 4:
        return min(SEV_GHICHU, sev + 1)
    return sev


def cap_theo_ket_luan(sev, ket_luan):
    """Khong duoc gan muc CHET cho mot dong ma tool CHUA ket luan duoc.

    Muc do va ket luan la hai tang khac nhau, nhung de trong bao cao mot dong
    vua ghi "Phai check tay" vua to do dam "CHET" thi nguoi doc hieu nham la
    link da mat. Nhom chua ket luan duoc cao nhat chi den NANG.
    """
    if ket_luan == V_CHECK:
        return max(SEV_NANG, sev)
    return sev


# ----------------------------------------------------------------- canh bao phu
# Mot link co the vua nofollow vua tro sai URL. Ma loi chinh chi lay cai nang nhat,
# nen liet ke phan con lai o cot rieng de khong bo sot khi kiem tra tay.
def secondary(res, page, primary=""):
    page = page or {}
    if res.status != "FOUND":
        return []
    out = []
    rel = (res.rel or "").lower()
    if any(r in rel for r in NOFOLLOW_REL):
        out.append("NOFOLLOW")
    if res.indexable == "no":
        out.append("CANONICAL_KHAC" if "canonical" in (res.note or "").lower()
                   else "TRANG_NOINDEX")
    if page.get("domain_only_match") or "sai URL dich" in (res.note or ""):
        out.append("SAI_URL_DICH")
    if page.get("sai_tang"):
        out.append("TRO_SAI_TANG")
    if page.get("via_redirect"):
        out.append("LINK_QUA_TRUNG_GIAN")
    if page.get("outbound", 0) > 150:
        out.append("TRANG_NHIEU_LINK_RA")
    a = (res.anchor_text or "").strip()
    if not a or a == "(anh / rong)":
        out.append("ANCHOR_RONG")
    elif a.lower().startswith(("http://", "https://", "www.")):
        out.append("ANCHOR_LA_URL")
    return [c for c in out if c != primary]
