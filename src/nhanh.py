"""
Danh dau link song nhung do vao mot URL tang tren DA CHET.

Tool check tung link mot cach doc lap: link tang 3 tro dung vao URL tang 2
thi tang 3 do "Link con". Nhung gia tri SEO chay theo chuoi - tang 3 -> tang 2
-> money site. URL tang 2 da chet thi moi link tang 3 do vao no deu dung lai o
do, du tung link van nguyen ven.

Module nay noi cac tang lai voi nhau: voi moi link song co 'khop_tang' la mot
tier, tra xem URL no tro toi da duoc check chua va ket luan ra sao. Nguon tra
cuu la ket qua cua CHINH dot chay nay (moi nhat), bo sung bang file CSV moi
nhat trong results/ cho nhung tier khong chay lan nay (vd 'run -t 4').

Khong doi ket luan cua link tang duoi - no van "Link con", khong phai loi cua
ben dat link do va khong dua vao yeu cau bu. Chi nang muc do va ghi ro URL
tang tren nao dang keo ca nhanh xuong.
"""

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import diagnose as D
import urlutil as U


def _doc_csv_moi_nhat(cfg):
    """normalize(url) -> (tier, ket_luan, diag_code) tu CSV moi nhat moi tier."""
    d = Path(cfg.output.get("dir", "results"))
    if not d.exists():
        return {}
    moi_nhat = {}
    for p in d.glob("*_%s_tier*.csv" % cfg.site_name):
        tier = p.stem.rsplit("_tier", 1)[1]
        cu = moi_nhat.get(tier)
        if cu is None or p.stat().st_mtime > cu.stat().st_mtime:
            moi_nhat[tier] = p
    out = {}
    for p in moi_nhat.values():
        with open(p, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if not r.get("source_url"):
                    continue
                code = (r.get("diag_code") or "").strip()
                v = (r.get("ket_luan") or "").strip() or (
                    D.verdict_of(code)[0] if code else D.V_CHECK)
                out[U.normalize(r["source_url"])] = (r.get("tier", ""), v, code)
    return out


def ban_do(cfg, results_by_tier=None):
    """Tra cuu ket luan cua moi URL da check. Ket qua dot nay de len CSV cu."""
    out = _doc_csv_moi_nhat(cfg)
    for rs in (results_by_tier or {}).values():
        for r in rs:
            if r.diag_code:
                out[U.normalize(r.source_url)] = (r.tier, r.ket_luan, r.diag_code)
    return out


def danh_dau(results, cfg, bd, finalize):
    """Ghi cot dich_tang_tren, chan doan lai nhung dong co nhanh tren da chet.

    finalize: checker.finalize - truyen vao de tranh import vong.
    Tra ve so dong bi danh dau.
    """
    n = 0
    for r in results:
        page = getattr(r, "_page", None)
        if page is None:
            continue
        cu = page.pop("nhanh_tren_chet", None)
        kt = (r.khop_tang or "").strip()
        if r.status != "FOUND" or not kt.startswith("tier") or not r.points_to:
            r.dich_tang_tren = ""
            if cu:
                finalize(r, page, cfg, getattr(r, "_use_js", False))
            continue
        info = bd.get(U.normalize(r.points_to))
        if not info:
            r.dich_tang_tren = "chua check"
        else:
            _tier, v, code = info
            if v == D.V_MAT:
                page["nhanh_tren_chet"] = code
                r.dich_tang_tren = "DA CHET (%s)" % code
                n += 1
            elif v == D.V_SONG:
                r.dich_tang_tren = "con song"
            else:
                r.dich_tang_tren = "chua ro (%s)" % code
        if page.get("nhanh_tren_chet") or cu:
            giu = r.dich_tang_tren
            finalize(r, page, cfg, getattr(r, "_use_js", False))
            r.dich_tang_tren = giu
    return n


def top_url_chet(results, n=10):
    """URL tang tren da chet -> so link tang duoi dang do vao, nhieu nhat truoc."""
    dem = Counter()
    for r in results:
        if (r.dich_tang_tren or "").startswith("DA CHET"):
            dem[r.points_to] += 1
    return dem.most_common(n)
