"""
Va lai DNS khi router / nha mang tra ve dia chi bat coc.

VAN DE THAT, do duoc ngay 2026-09-06 tren mot may chay tool:

    huthamctp.jimdosite.com  ->  127.0.0.1        (hoi router 192.168.0.1)
                             ->  162.159.129.70   (hoi 8.8.8.8, dia chi that)

Router tra ve 127.0.0.1 tuc la "chinh may nay". Tool go cua chinh no roi bao
KET_NOI_TU_CHOI. Ca 24 dong KET_NOI_TU_CHOI trong dot chay hom do deu la vay -
khong mot truong hop tu choi ket noi that nao.

VI SAO PHAI VA O TANG DNS chu khong chi doi ten ma loi:

Neu may dang chay bat ky web server nao nghe cong 443 (XAMPP, Docker, mot dev
server bo quen), thi local server se TRA LOI THAY cho ten mien bi bat coc. Tool
nhan HTTP 200, doc mot trang HTML la, khong thay the <a> nao ve money site, roi
ket luan LINK_BI_GO - "admin da go link, dang lai". Do la ket luan SAI, mau do,
tinh vao tien doi bu, va khong co dau hieu gi de nhan ra. Bit ngay tu tang DNS
thi ca hai kieu hong - on ao va im lang - deu bien mat.

CACH LAM: hoi lai bang DNS-over-HTTPS (di thang qua HTTPS nen router khong xen
vao duoc), roi ep socket dung IP that cho dung nhung host do. Chromium o luot
render duoc truyen cung bang IP do qua --host-resolver-rules.

GIOI HAN: chi va duoc kieu chan bang DNS. Neu duong truyen con loc theo ten
mien - noi duoc toi IP that nhung vua khai ten mien la bi cat - thi khong tool
nao vuot qua duoc. Truong hop do duoc danh dau rieng de ben chan doan ra ma
MANG_CUA_BAN_CHAN, thay vi de nguoi doc tuong link da chet.
"""

import asyncio
import ipaddress
import socket
import sys

# Cac dich vu DNS-over-HTTPS dung de hoi lai. Deu tra ve JSON cung dinh dang.
DOH = (
    "https://dns.google/resolve",
    "https://cloudflare-dns.com/dns-query",
)
DOH_TIMEOUT = 8.0


def la_dia_chi_bat_coc(ip: str) -> bool:
    """Dia chi nay co phai cau tra loi "chan" thay vi dia chi that khong?

    Chi bat loopback (127.x, ::1) va dia chi rong (0.0.0.0, ::). Day la hai thu
    khong mot website cong cong nao dung that, nen ket luan chac chan.

    CO Y khong bat dai IP noi bo (192.168.x, 10.x): mot so cong ty dung
    split-DNS hop le tro ten mien that ve may chu trong mang. Bat ca dai do se
    pha nhung moi truong do.
    """
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.is_loopback or a.is_unspecified


async def _hoi_doh(client, host: str):
    """Hoi dia chi that qua DNS-over-HTTPS. Tra ve IP dau tien, hoac None."""
    for url in DOH:
        try:
            r = await client.get(url, params={"name": host, "type": "A"},
                                 headers={"accept": "application/dns-json"},
                                 timeout=DOH_TIMEOUT)
            if r.status_code != 200:
                continue
            for a in (r.json().get("Answer") or []):
                # type 1 = ban ghi A. Bo qua CNAME (type 5) o giua chuoi.
                if a.get("type") == 1 and not la_dia_chi_bat_coc(a.get("data", "")):
                    return a["data"]
        except Exception:
            continue
    return None


class VaDNS:
    """Nho ket qua kiem tra DNS theo host va ep socket dung IP that.

    Moi host chi kiem tra MOT lan cho ca dot chay: tra loi DNS khong doi giua
    chung, ma tier 4 co 641 host nen hoi lai theo tung link la lang phi.
    """

    def __init__(self, bat=True):
        self.bat = bat
        self._ip = {}            # host -> ip that (chi host da duoc va)
        self._bat_coc = set()    # host bi tra ve dia chi bat coc
        self._da_xet = set()
        self._locks = {}
        self._goc = None

    # ------------------------------------------------------------- kiem tra
    async def dam_bao(self, client, host: str):
        """Kiem tra host mot lan, va lai neu bi bat coc. Goi truoc khi tai trang."""
        if not self.bat or not host or host in self._da_xet:
            return
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            if host in self._da_xet:
                return
            try:
                ip = await asyncio.to_thread(socket.gethostbyname, host)
            except Exception:
                # Khong phan giai duoc la chuyen khac (domain het han) - de
                # nguyen cho chan doan xu ly, khong dinh vao day.
                self._da_xet.add(host)
                return
            if not la_dia_chi_bat_coc(ip):
                self._da_xet.add(host)
                return
            self._bat_coc.add(host)
            that = await _hoi_doh(client, host)
            if that:
                self._ip[host] = that
                self._cai_patch()
            self._da_xet.add(host)

    def bi_bat_coc(self, host: str) -> bool:
        """DNS cua may tra ve dia chi bat coc cho host nay?"""
        return host in self._bat_coc

    # --------------------------------------------------------------- socket
    def _cai_patch(self):
        """Ep socket.getaddrinfo tra ve IP that cho dung cac host da va.

        Doi host thanh IP o day KHONG lam hong HTTPS: httpx van dung ten mien
        goc lam SNI va header Host, chung khong lay tu getaddrinfo. Chung chi
        van duoc kiem tra dung ten mien.
        """
        if self._goc is not None:
            return
        self._goc = socket.getaddrinfo
        bang = self._ip

        def getaddrinfo(host, port, *a, **kw):
            return self._goc(bang.get(host, host), port, *a, **kw)

        socket.getaddrinfo = getaddrinfo

    def go_patch(self):
        if self._goc is not None:
            socket.getaddrinfo = self._goc
            self._goc = None

    # ------------------------------------------------------------- chromium
    def host_resolver_rules(self):
        """Co dong lenh cho Chromium, hoac None neu khong co gi phai va.

        Chromium chay o tien trinh rieng nen khong dinh gi toi socket cua
        Python - phai truyen bang anh xa rieng cho no.
        """
        if not self._ip:
            return None
        return "--host-resolver-rules=" + ",".join(
            "MAP %s %s" % (h, ip) for h, ip in sorted(self._ip.items()))

    # ---------------------------------------------------------------- bao cao
    def tom_tat(self):
        """(so host da va duoc, so host bi bat coc ma khong va duoc)."""
        return len(self._ip), len(self._bat_coc) - len(self._ip)

    def in_bao_cao(self, quiet=False):
        if quiet or not self._bat_coc:
            return
        va, chiu = self.tom_tat()
        if va:
            print("DNS: %d ten mien bi tra ve dia chi bat coc, da va bang dia chi "
                  "that (%s). Va DNS khong bao dam vao duoc: link nao van bi cat "
                  "ket noi se mang ma MANG_CUA_BAN_CHAN - mang chan, KHONG phai "
                  "link chet." % (va, ", ".join(sorted(self._ip))), file=sys.stderr)
        if chiu:
            con = sorted(self._bat_coc - set(self._ip))
            print("DNS: %d ten mien bi chan ma khong lay duoc dia chi that (%s). "
                  "Cac link nay se mang ma MANG_CUA_BAN_CHAN, KHONG phai link chet."
                  % (chiu, ", ".join(con)), file=sys.stderr)
