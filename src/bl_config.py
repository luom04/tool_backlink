"""
Doc va validate file cau hinh YAML cho backlink checker.

Moi site la mot file YAML trong config/. Tat ca tham so truoc day hardcode
trong checker.py (money domain, tier, concurrency, delay...) nay nam o day.
"""

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

DEFAULTS = {
    "network": {
        "concurrency": 8,
        "per_domain_delay": 1.5,
        "timeout": 25,
        "retries": 1,
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
        self.master_csv = src.get("master_csv", "data/backlinks_master.csv")

        merged = _deep_merge(DEFAULTS, {k: raw.get(k) for k in
                                        ("network", "js", "ingest", "output")
                                        if raw.get(k) is not None})
        self.network = merged["network"]
        self.js = merged["js"]
        self.ingest = merged["ingest"]
        self.output = merged["output"]

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

    def _validate_delay(self):
        d = self.network["per_domain_delay"]
        if d < 1.0:
            print(f"CANH BAO: per_domain_delay = {d}s (< 1.0s). Rat de bi ban IP "
                  f"o cac tang co nhieu link chung mot domain.", file=sys.stderr)

    def tier_for_sheet(self, sheet: str):
        """Tu khoa khop dai nhat thang - tranh viec 'Submiss Web 2.0 tang 3'
        bi gan nham vao tier 2 chi vi chua chuoi 'web 2.0'."""
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
