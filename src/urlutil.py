"""Chuan hoa URL dung chung cho ingest, checker va report."""

import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

TRACKING_PREFIX = ("utm_", "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid",
                   "igshid", "ref_src", "spm", "yclid", "_ga", "_gl")

URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"'\)\]\},;]+", re.I)
ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍﻿ "), None)


def clean_raw(url: str) -> str:
    """Lam sach chuoi URL tho lay tu Excel / Google Docs."""
    if not url:
        return ""
    u = str(url).translate(ZERO_WIDTH).strip().strip("\"'<>")
    u = re.sub(r"\s+", "", u)
    u = u.rstrip(".,;:)]}")
    if u.lower().startswith("www."):
        u = "https://" + u
    if u.startswith("//"):
        u = "https:" + u
    if not u.lower().startswith(("http://", "https://")):
        return ""
    return u


def is_valid(url: str, min_len: int = 12) -> bool:
    if len(url) < min_len:
        return False
    p = urlparse(url)
    host = p.netloc.split("@")[-1].split(":")[0]
    if "." not in host or host.startswith(".") or host.endswith("."):
        return False
    if re.search(r"[\s]", host):
        return False
    return True


def normalize(url: str, strip_tracking: bool = True) -> str:
    """Dang so sanh: bo scheme, bo www, bo slash cuoi, bo tham so tracking."""
    if not url:
        return ""
    p = urlparse(url.strip())
    host = (p.netloc or "").lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    path = p.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    pairs = parse_qsl(p.query, keep_blank_values=True)
    if strip_tracking:
        pairs = [(k, v) for k, v in pairs
                 if not any(k.lower().startswith(t) for t in TRACKING_PREFIX)]
    return urlunparse(("", host, path, "", urlencode(sorted(pairs)), ""))


def domain_of(url: str) -> str:
    h = (urlparse(url).netloc or "").lower().split("@")[-1].split(":")[0]
    return h[4:] if h.startswith("www.") else h


def registrable(url_or_host: str) -> str:
    """Xap xi domain goc: bo subdomain, giu 2 nhan cuoi (3 voi .com.vn, .co.uk...)."""
    h = url_or_host if "://" not in url_or_host else domain_of(url_or_host)
    parts = h.split(".")
    if len(parts) <= 2:
        return h
    two = ".".join(parts[-2:])
    if parts[-2] in ("com", "co", "net", "org", "gov", "edu") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return two


def extract_urls(text: str) -> list:
    """Tim moi URL nam trong mot doan van ban tu do."""
    out = []
    for m in URL_RE.finditer(text or ""):
        u = clean_raw(m.group(0))
        if u:
            out.append(u)
    return out
