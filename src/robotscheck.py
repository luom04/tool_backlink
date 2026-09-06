"""
Doc robots.txt de tra loi mot cau duy nhat: GOOGLEBOT co duoc phep vao URL nay khong.

Khac han cau hoi "tool co doc duoc trang khong". Mot trang co the mo binh thuong,
the <a> con nguyen, dofollow, index duoc - nhung neu robots.txt cam Googlebot thu
thap duong dan do thi Google khong bao gio ghe vao, va backlink khong truyen duoc
chut gia tri nao. Vi du that trong du an nay: penzu.com cam han "/p/", ma ca ba
backlink tier 2 tren penzu deu la "/p/...".

Nguyen tac an toan xuyen suot file nay: CHI ket luan "bi chan" khi doc duoc
robots.txt sach se (HTTP 200) va luat noi ro rang. Moi truong hop con lai (mat
mang, 403, 500, file rac) deu tra ve KHONG_RO - tool khong doi bu tren mot suy
doan.
"""

import asyncio
import re
from urllib.parse import urlsplit, unquote

CHO_PHEP = "cho phep"
BI_CHAN = "bi chan"
KHONG_RO = "khong ro"

# Ten bot ta dong vai khi doc luat. Google dung "Googlebot" cho tim kiem web.
BOT = "googlebot"


# --------------------------------------------------------------- so khop duong dan
def _thanh_regex(mau: str) -> re.Pattern:
    """Doi mot mau trong robots.txt thanh regex.

    Google ho tro dung hai ky tu dac biet:
        *  khop voi bat ky chuoi nao (ke ca rong)
        $  danh dau ket thuc duong dan
    Cac ky tu con lai deu la nghia den. urllib.robotparser cua Python KHONG xu ly
    "*" nam giua duong dan, nen o day tu viet de khong bo sot luat kieu
    "Disallow: /*?replytocom".
    """
    ket_thuc = mau.endswith("$")
    than = mau[:-1] if ket_thuc else mau
    bo_phan = [re.escape(p) for p in than.split("*")]
    pat = ".*".join(bo_phan)
    return re.compile("^" + pat + ("$" if ket_thuc else ""))


class LuatRobots:
    """Cac luat rut ra tu mot file robots.txt, da chon dung nhom cho Googlebot."""

    def __init__(self, allow=None, disallow=None, doc_duoc=True):
        self.allow = allow or []          # [(do_dai_mau, regex)]
        self.disallow = disallow or []
        self.doc_duoc = doc_duoc

    def cho_phep(self, path: str) -> str:
        if not self.doc_duoc:
            return KHONG_RO
        # Google: luat co mau DAI NHAT thang. Hoa nhau thi Allow thang Disallow.
        dai_allow = max((n for n, rx in self.allow if rx.match(path)), default=-1)
        dai_disallow = max((n for n, rx in self.disallow if rx.match(path)), default=-1)
        if dai_disallow < 0:
            return CHO_PHEP
        if dai_allow >= dai_disallow:
            return CHO_PHEP
        return BI_CHAN


def phan_tich(text: str) -> LuatRobots:
    """Doc noi dung robots.txt -> LuatRobots danh cho Googlebot.

    Nhom "googlebot" duoc uu tien; khong co thi dung nhom "*". Nhom nao khong
    lien quan thi bo qua hoan toan.
    """
    nhom = {}          # ten bot -> {"allow": [...], "disallow": [...]}
    dang_ap = []       # cac ten bot cua khoi User-agent dang doc
    vua_khai_bot = False

    for dong in text.splitlines():
        dong = dong.split("#", 1)[0].strip()
        if not dong or ":" not in dong:
            continue
        khoa, _, gia_tri = dong.partition(":")
        khoa = khoa.strip().lower()
        gia_tri = gia_tri.strip()

        if khoa == "user-agent":
            # Nhieu dong User-agent lien tiep = cung mot nhom luat.
            if not vua_khai_bot:
                dang_ap = []
            dang_ap.append(gia_tri.lower())
            nhom.setdefault(gia_tri.lower(), {"allow": [], "disallow": []})
            vua_khai_bot = True
            continue

        vua_khai_bot = False
        if khoa not in ("allow", "disallow") or not dang_ap:
            continue
        # "Disallow:" bo trong nghia la khong cam gi ca - bo qua.
        if khoa == "disallow" and gia_tri == "":
            continue
        if not gia_tri.startswith("/"):
            continue
        for bot in dang_ap:
            nhom[bot][khoa].append((len(gia_tri), _thanh_regex(gia_tri)))

    chon = nhom.get(BOT) or nhom.get("*")
    if chon is None:
        # Khong co nhom nao ap dung cho ta -> khong bi cam gi.
        return LuatRobots()
    return LuatRobots(chon["allow"], chon["disallow"])


# --------------------------------------------------------------- bo nho dem
# Tai robots.txt hong thi thu lai. Con so nho vi moi host chi tai MOT lan cho
# ca dot chay: 494 host khong doc duoc x 1 lan thu them = 494 request, khong
# dang ke so voi 2691 link.
SO_LAN_THU = 2
NGHI_GIUA_HAI_LAN = 1.0


class BoNhoRobots:
    """Tai robots.txt moi host dung MOT lan roi dung lai cho moi link cung host.

    Tier 4 co 1.045 link tren 641 host, nen tai lai theo tung link se gan nhu
    nhan doi so request cua luot 1. Khoa theo host, co lock rieng tung host de
    hai coroutine cung host khong cung luc di tai.
    """

    def __init__(self, timeout=10.0):
        self.timeout = timeout
        self._luat = {}
        self._locks = {}

    async def _tai(self, client, scheme, host):
        """Tai robots.txt cua mot host. Ket qua duoc nho lai cho CA dot chay.

        Vi ket qua duoc nho lai, mot lan hong vat lam hong ket luan cua MOI
        link tren host do - va hong theo huong dat tien: link dang tu
        ROBOTS_CHAN_GOOGLE ("Link mat", doi bu duoc) tut xuong "phai check tay".
        Chuyen nay da xay ra that voi penzu.com ngay 2026-09-06: lan chay 18:15
        doc duoc "Disallow: /p/" va cho ROBOTS_CHAN_GOOGLE, lan 18:35 tai hong
        nen ca 3 link penzu tang 2 tut xuong TIMEOUT.

        Nen o day thu lai, khac han lop kiem tra trang: mot request robots.txt
        la mot lan cho ca host chu khong phai moi link mot lan, nen gia cua
        viec thu lai gan nhu bang khong.
        """
        url = "%s://%s/robots.txt" % (scheme, host)
        for lan in range(SO_LAN_THU):
            cuoi = lan == SO_LAN_THU - 1
            try:
                r = await client.get(url, follow_redirects=True,
                                     timeout=self.timeout)
            except Exception:
                if cuoi:
                    return LuatRobots(doc_duoc=False)
                await asyncio.sleep(NGHI_GIUA_HAI_LAN)
                continue
            if r.status_code != 200:
                # 404 nghia la khong co luat nao - Google coi nhu duoc phep het.
                # Day la ket qua CHAC CHAN, tra ve ngay khong thu lai.
                if r.status_code in (404, 410):
                    return LuatRobots()
                # 403 la quyet dinh cua may chu, thu lai cung the. Chi 5xx va
                # 429 moi la loi tam thoi dang thu lai.
                if r.status_code >= 500 or r.status_code == 429:
                    if not cuoi:
                        await asyncio.sleep(NGHI_GIUA_HAI_LAN)
                        continue
                return LuatRobots(doc_duoc=False)
            ctype = (r.headers.get("content-type") or "").lower()
            text = r.text
            # Nhieu site tra ve trang HTML 200 thay cho robots.txt that. Doc no
            # nhu luat se cho ket qua bay ba, nen coi la khong ro. Day cung la
            # cau tra loi on dinh cua may chu, khong thu lai.
            if "html" in ctype or text.lstrip()[:1] == "<":
                return LuatRobots(doc_duoc=False)
            return phan_tich(text)
        return LuatRobots(doc_duoc=False)

    async def trang_thai(self, client, url: str) -> str:
        """-> CHO_PHEP / BI_CHAN / KHONG_RO cho dung URL nay."""
        p = urlsplit(url)
        if not p.hostname:
            return KHONG_RO
        khoa = "%s://%s" % (p.scheme or "https", p.netloc)
        lock = self._locks.setdefault(khoa, asyncio.Lock())
        async with lock:
            if khoa not in self._luat:
                self._luat[khoa] = await self._tai(client, p.scheme or "https",
                                                   p.netloc)
        path = p.path or "/"
        if p.query:
            path += "?" + p.query
        return self._luat[khoa].cho_phep(unquote(path))
