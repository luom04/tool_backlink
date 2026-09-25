"""
Doc va validate file cau hinh YAML cho backlink checker.

Moi site la mot file YAML trong config/. Tat ca tham so truoc day hardcode
trong checker.py (money domain, tier, concurrency, delay...) nay nam o day.
"""

import os
import re
import sys
import unicodedata
from pathlib import Path

import yaml


def fold(s: str) -> str:
    """Bo dau tieng Viet + ve chu thuong, de so khop ten tab khong phu thuoc dau."""
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "d").lower().strip()

# So tang viet thang trong ten tab: "TANG 2", "Tier 2", "tang 4_bookmarks",
# "Social Bookmarks DA cao tang 3". Dau phan cach co the la khoang trang, gach
# ngang, gach duoi hoac hai cham.
TIER_TOKEN_RE = re.compile(r"(?:tang|tier)\s*[:\-_]?\s*([1-9])")

# Tran so tab Chromium song song. TRAN_JS_AUTO la muc che do "auto" tu chon,
# TRAN_JS la tran cung cho ca gia tri nguoi dung tu dien.
TRAN_JS_AUTO = 4
TRAN_JS = 6

DEFAULTS = {
    "network": {
        "concurrency": 8,
        "per_domain_delay": 1.5,
        "timeout": 25,
        "retries": 1,
        # Router/nha mang co the tra ve 127.0.0.1 cho ten mien bi chan. Bat cai
        # nay thi tool tu hoi lai dia chi that qua DNS-over-HTTPS. Xem dnsfix.py.
        "dns_fallback": True,
        "verify_ssl": False,
        "user_agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    },
    "js": {
        "auto_tiers": [],
        "force_domains": [],
        # domcontentloaded + cho them wait_after: networkidle bi treo tren cac
        # trang co polling (mn.co, penzu...) va lam hong ca buoc render.
        "wait_until": "domcontentloaded",
        "wait_after": 6000,
        "timeout": 40000,
        # So tab Chromium chay song song o luot render. "auto" = tu do theo may.
        # Luot render la khau cham nhat ca dot chay (mot tab tuan tu ngon ~75%
        # tong thoi gian), nen day la cho dang de song song nhat.
        "concurrency": "auto",
        # Luot 1 doc HTML tho cho moi link. Link nao dinh mot trong cac tin hieu
        # duoi day thi moi mo Chromium o luot 2 - nhanh hon nhieu so voi render
        # tat ca, ma van khong bo sot trang can JS.
        "escalate": True,
    },
    "ingest": {
        "drop_sheets": [],
        "drop_domains": [],
        "dedupe": True,
        "strip_tracking": True,
        "min_url_length": 12,
        "sheet_columns": {},
        "warn_homepage_urls": True,
    },
    "robots": {
        # Doc robots.txt cua tung host de biet Googlebot co duoc phep vao URL do
        # khong. Tra loi cau hoi khac han "tool co doc duoc trang khong": trang
        # mo binh thuong ma bi robots.txt cam thi Google khong ghe vao, backlink
        # khong truyen duoc gia tri nao.
        "check": True,
        # Moi host chi tai robots.txt mot lan roi dung lai, nen chi phi la
        # +1 request/host chu khong phai +1 request/link.
        "timeout": 10,
    },
    "googlebot": {
        # Tai lai moi URL voi tu cach Googlebot va ket luan theo nhung gi Google
        # thay. Bat phat hien trang tra 404 rieng cho Google, link giau voi
        # Google, va nguoi dung bi chuyen di trong khi Google van thay link.
        # Ton them mot request moi URL (van xep hang theo per_domain_delay).
        "check": True,
    },
    "output": {
        "dir": "results",
        "formats": ["csv", "xlsx"],
        "filename": "{date}_{site}_tier{tier}",
    },
}


class ConfigError(Exception):
    pass


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Tier:
    """Mot tang trong kim tu thap."""

    def __init__(self, num: int, raw: dict):
        self.num = num
        self.label = raw.get("label", f"Tier {num}")
        self.match = [fold(m) for m in (raw.get("match") or [])]
        self.js = raw.get("js")               # None = theo config chung
        self.priority = raw.get("priority", num)
        self.note = raw.get("note", "")

        # targets nhan mot gia tri hoac mot danh sach:
        #   targets: money
        #   targets: "tier:2"
        #   targets: [money, "tier:2"]
        # Danh sach = "link cua tang nay tro vao BAT KY dich nao trong day deu
        # duoc tinh la dat". Thu tu quyet dinh nhan ghi o cot khop_tang khi mot
        # URL thuoc nhieu tap cung luc.
        raw_t = raw.get("targets", "money")
        items = raw_t if isinstance(raw_t, (list, tuple)) else [raw_t]
        self.targets = []
        for t in items:
            t = str(t).strip()
            if t.startswith("tier:"):
                try:
                    self.targets.append(("tier", int(t.split(":", 1)[1])))
                except ValueError:
                    raise ConfigError(
                        f"tier {num}: '{t}' sai dinh dang, phai la 'tier:<so>'")
            elif t in ("money", "money_site"):
                self.targets.append(("money", None))
            else:
                raise ConfigError(
                    f"tier {num}: targets phai la 'money' hoac 'tier:N' "
                    f"(hoac danh sach gom hai loai do), dang co '{t}'")
        if not self.targets:
            raise ConfigError(f"tier {num}: targets rong")

        # Giu lai hai thuoc tinh cu cho phan code khac van doc chung.
        self.targets_kind, self.targets_tier = self.targets[0]

    def match_score(self, sheet: str) -> int:
        """0 = khong khop. Lon hon = tu khoa khop dai hon = dac trung hon."""
        s = fold(sheet)
        hits = [len(m) for m in self.match if m and m in s]
        return max(hits) if hits else 0

    def matches_sheet(self, sheet: str) -> bool:
        return self.match_score(sheet) > 0


class Config:
    def __init__(self, raw: dict, path: Path):
        self.path = path
        self.raw = raw

        site = raw.get("site") or {}
        self.site_name = site.get("name") or path.stem
        money = site.get("money_domain")
        if not money:
            raise ConfigError("thieu site.money_domain")
        self.money_domain = money.lower().replace("https://", "").replace(
            "http://", "").replace("www.", "").strip("/")
        self.target_urls = [u.strip() for u in (site.get("target_urls") or []) if u.strip()]
        self.extra_domains = [d.lower().replace("www.", "")
                              for d in (site.get("extra_domains") or [])]

        src = raw.get("source") or {}
        self.source_type = src.get("type", "csv")
        self.source_url = src.get("url", "")
        self.source_file = src.get("file", "")
        # {site} trong duong dan duoc thay bang site.name, de file mau khai
        # mot lan la dung cho moi du an ma khong so hai du an ghi de nhau.
        # Giu nguyen mac dinh cu cho cac config da co san khong khai muc nay.
        self.master_csv = src.get("master_csv", "data/backlinks_master.csv"
                                  ).replace("{site}", self.site_name)

        merged = _deep_merge(DEFAULTS, {k: raw.get(k) for k in
                                        ("network", "js", "ingest", "output",
                                         "robots", "googlebot")
                                        if raw.get(k) is not None})
        self.network = merged["network"]
        self.js = merged["js"]
        self.ingest = merged["ingest"]
        self.output = merged["output"]
        self.robots = merged["robots"]
        self.googlebot = merged["googlebot"]

        tiers_raw = raw.get("tiers") or {}
        if not tiers_raw:
            raise ConfigError("thieu muc 'tiers'")
        self.tiers = {}
        for k, v in tiers_raw.items():
            n = int(k)
            self.tiers[n] = Tier(n, v or {})

        for n, t in self.tiers.items():
            for kind, num in t.targets:
                if kind != "tier":
                    continue
                if num not in self.tiers:
                    raise ConfigError(
                        f"tier {n} tro ve tier {num} nhung tier do khong ton tai")
                if num > n:
                    raise ConfigError(
                        f"tier {n} khong the tro ve tier {num} - do la tang duoi. "
                        f"Link chi duoc tro len tang tren hoac trong cung mot tang.")
                if num == n and len(t.targets) == 1:
                    raise ConfigError(
                        f"tier {n} chi khai dich la chinh no - se khong bao gio "
                        f"khop. Them 'money' hoac mot tang tren vao targets.")

        self._validate_delay()

    def js_concurrency(self) -> int:
        """So tab Chromium chay song song o luot render.

        "auto" = min(TRAN_JS_AUTO, so CPU // 2). Tool nay duoc dung chung tren
        nhieu may nen mac dinh phai an toan cho may yeu nhat: may 2 nhan ra 1
        tab, dung bang hanh vi tuan tu cu; may 12 nhan ra 4 tab.

        Tran cung TRAN_JS: moi tab ton khoang 300MB RAM. Vuot qua day khong
        nhanh them bao nhieu vi luot render con bi domain lock ham lai, nhung
        du de treo may nguoi khac.
        """
        v = self.js.get("concurrency", "auto")
        if isinstance(v, str) and v.strip().lower() == "auto":
            return self._js_auto()
        try:
            n = int(v)
        except (TypeError, ValueError):
            print(f"CANH BAO: js.concurrency = {v!r} khong phai so - dung auto.",
                  file=sys.stderr)
            return self._js_auto()
        if n < 1:
            return 1
        if n > TRAN_JS:
            print(f"CANH BAO: js.concurrency = {n} vuot tran {TRAN_JS} - ha xuong "
                  f"{TRAN_JS}. Nhieu tab hon chi ton RAM chu khong nhanh them.",
                  file=sys.stderr)
            return TRAN_JS
        return n

    @staticmethod
    def _js_auto() -> int:
        return max(1, min(TRAN_JS_AUTO, (os.cpu_count() or 2) // 2))

    def _validate_delay(self):
        d = self.network["per_domain_delay"]
        if d < 1.0:
            print(f"CANH BAO: per_domain_delay = {d}s (< 1.0s). Rat de bi ban IP "
                  f"o cac tang co nhieu link chung mot domain.", file=sys.stderr)

    def tier_for_sheet(self, sheet: str):
        """Ten tab -> so tier.

        Hai buoc, theo dung thu tu:

        1. Ten tab co ghi thang so tang ("TANG 2", "Tier 2", "tang 4_bookmarks")
           thi lay luon so do. Khai bao ro rang nhat phai thang.
        2. Khong co thi moi xet 'match', tu khoa khop DAI NHAT thang - de
           'Submiss Web 2.0 tang 3' khong bi keo ve tier 2 chi vi chua 'web 2.0'.

        Vi sao buoc 1 phai dung truoc: file config cua du an dang chay co ca tu
        khoa cu ("web 2.0", "backlink domain dr cao") lan token tang. Khi ben
        cung cap doi ten tab sang quy uoc moi, "TANG 3 - WEB 2.0" se co ca hai,
        va "web 2.0" (7 ky tu) dai hon "tang 3" (6) nen thang - tab tang 3 bi
        gan vao tier 2. Cho token tang thang truoc thi mot file config chay
        duoc voi ca ten tab cu lan ten tab moi, khong phai sua gi khi chuyen.
        """
        m = TIER_TOKEN_RE.search(fold(sheet))
        if m and int(m.group(1)) in self.tiers:
            return int(m.group(1))
        best, best_score = None, 0
        for n in sorted(self.tiers):
            sc = self.tiers[n].match_score(sheet)
            if sc > best_score:
                best, best_score = n, sc
        return best

    def js_for_tier(self, tier: int, cli_flag: bool) -> bool:
        if cli_flag:
            return True
        t = self.tiers.get(int(tier))
        if t and t.js is not None:
            return bool(t.js)
        return int(tier) in [int(x) for x in (self.js.get("auto_tiers") or [])]

    def force_js_domain(self, host: str) -> bool:
        h = (host or "").lower()
        return any(h.endswith(d.lstrip("*")) or d.lstrip("*.") in h
                   for d in (self.js.get("force_domains") or []))

    def out_path(self, date: str, tier, ext: str) -> Path:
        name = self.output["filename"].format(
            date=date, site=self.site_name, tier=tier if tier else "all")
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
        return Path(self.output["dir"]) / f"{name}.{ext}"


def load(path) -> Config:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"khong tim thay file config: {p}")
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return Config(raw, p)
