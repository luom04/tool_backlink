"""
Doi soat nguon backlink voi ben cung cap.

Tra loi dung mot cau hoi: ho noi giao N link, thuc te ta nhan duoc bao nhieu
link dung nghia, va bao nhieu link ho phai bu lai.

Mot link duoc coi la KHONG giao duoc khi roi vao mot trong bon truong hop:
    1. Trung lap      - cung mot URL dem hai lan
    2. Tro ve money site - do la link cua chinh ta, khong phai backlink
    3. URL hong       - khong phai URL hop le, khong mo duoc
    4. Chet khi check - 404 / 410 / domain het han / bai bi go

Rieng nhom "phai check tay" KHONG dua vao yeu cau bu: tool chua doc duoc
noi dung that nen chua co bang chung, doi kiem tra xong da.

Chay:
    python src/doisoat.py -c config/checkbacklink.yaml
    python src/doisoat.py -c config/checkbacklink.yaml -o results/doi-soat.xlsx
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bl_config
import diagnose as D
import ingest as ingest_mod
import urlutil as U

# Cac khoan duoc tinh vao de nghi bu, theo dung thu tu hien tren bao cao.
KHOAN_BU = [
    ("trung",       "Link giao trung",
     "Cung mot URL xuat hien nhieu lan - chi tinh duoc mot"),
    ("money_site",  "Link tro ve chinh money site",
     "Day la link cua ta, khong phai backlink ben ngoai"),
    ("url_hong",    "URL hong / khong hop le",
     "O du lieu khong phai URL mo duoc"),
    ("chet",        "Link da chet khi kiem tra",
     "404 / 410 / domain het han / bai bi go / noindex / nofollow / canonical khac / "
     "can dang nhap moi xem"),
    ("khong_gia_tri", "Link khong truyen duoc gia tri (phu)",
     "Ket luan la Link con nhung van dinh noindex / nofollow / canonical khac"),
    ("sai_tang",     "Link tro sai tang",
     "Link song va dofollow, nhung roi vao tang khac voi tang ho khai giao"),
]

# Ma cho biet link tro khong dung tang da khai. Link van song, van dofollow,
# van truyen gia tri - nhung vao sai cho nen khong dung duoc theo so do.
#
# Truoc day khoan nay CO Y bi bo ra ngoai yeu cau bu, vi so rang ta khai
# 'targets' trong config sai chu khong phai ho dat link sai. Bang chung ngay
# 2026-09-06 lat lai lap luan do: chinh file cua ben cung cap khai o dong tieu
# de "Link Tang 3 tro ve Tang 2", va chinh nguoi check tay cua ta ghi ca 11/11
# dong tab 'submiss 2.0 tang 3' la "chua dung link tang 3". Hai ben doc lap
# cung noi mot chuyen, nen day khong con la suy doan.
MA_SAI_TANG = ("TRO_SAI_TANG",)

# Ma loi tuy van con the <a> nhung link khong truyen duoc gia tri SEO nao.
# Khi la ma loi CHINH, ca ba ma nay da duoc xep thang vao "Link mat" (xem VERDICT
# trong diagnose.py) nen roi vao khoan "chet". Danh sach duoi day chi con bat
# truong hop chung xuat hien o cot canh_bao_them - ma chinh la loi khac nhung
# trang van noindex / link van nofollow. Hai duong khong chong nhau: khoan nay
# chi cong them cho nhung dong co ket luan "Link con".
MA_KHONG_GIA_TRI = ("TRANG_NOINDEX", "NOFOLLOW", "CANONICAL_KHAC")


# ------------------------------------------------------------- doc ket qua check
def doc_ket_qua(cfg, thu_muc=None):
    """Gom ket qua check moi nhat cua tung tier trong thu muc results/.

    Moi tier lay dung file CSV moi nhat. Tra ve dict: source_url -> row.
    Chua chay check bao gio thi tra ve dict rong - bao cao van chay duoc,
    chi thieu phan link chet.
    """
    d = Path(thu_muc or cfg.output.get("dir", "results"))
    if not d.exists():
        return {}, []
    moi_nhat = {}
    for p in d.glob("*.csv"):
        ten = p.stem
        if "_tier" not in ten:
            continue
        tier = ten.rsplit("_tier", 1)[1]
        cu = moi_nhat.get(tier)
        if cu is None or p.stat().st_mtime > cu.stat().st_mtime:
            moi_nhat[tier] = p

    out = {}
    for p in moi_nhat.values():
        with open(p, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r.get("source_url"):
                    out[U.normalize(r["source_url"])] = r
    return out, sorted(p.name for p in moi_nhat.values())


def _ket_luan(row):
    """Ket luan cua mot dong ket qua. File cu chua co cot nay thi suy tu ma loi."""
    v = (row.get("ket_luan") or "").strip()
    if v:
        return v
    code = (row.get("diag_code") or "").strip()
    return D.verdict_of(code)[0] if code else D.V_CHECK


def _khong_gia_tri(row):
    """Dong ket luan "Link con" nhung trang noindex -> khong truyen gia tri."""
    if (row.get("diag_code") or "").strip() in MA_KHONG_GIA_TRI:
        return True
    them = (row.get("canh_bao_them") or "")
    return any(m in them for m in MA_KHONG_GIA_TRI)


def _sai_tang(row):
    """Dong ket luan "Link con" nhung tro vao tang khac voi khai bao."""
    return (row.get("diag_code") or "").strip() in MA_SAI_TANG


# ------------------------------------------------------------------- tong hop
def build(cfg, url="", thu_muc=None):
    rows, stats, unmatched, dups = ingest_mod.build(cfg, url, verbose=False)
    kq, file_kq = doc_ket_qua(cfg, thu_muc)

    # dem ket qua check theo tung tab nguon
    theo_tab = defaultdict(Counter)
    for r in rows:
        k = kq.get(U.normalize(r["source_url"]))
        if not k:
            theo_tab[r["sheet"]]["chua_check"] += 1
            continue
        v = _ket_luan(k)
        if v == D.V_SONG:
            theo_tab[r["sheet"]]["con"] += 1
            # elif chu khong phai if: mot link vua nofollow vua sai tang van
            # chi la MOT link thieu, dem hai lan la thoi phong yeu cau bu.
            # Uu tien khoan nang hon - khong truyen duoc chut gia tri nao.
            if _khong_gia_tri(k):
                theo_tab[r["sheet"]]["khong_gia_tri"] += 1
            elif _sai_tang(k):
                theo_tab[r["sheet"]]["sai_tang"] += 1
        elif v == D.V_MAT:
            theo_tab[r["sheet"]]["chet"] += 1
        else:
            theo_tab[r["sheet"]]["check_tay"] += 1

    bang = []
    for so in stats.per_sheet:
        c = theo_tab.get(so["tab"], Counter())
        d = dict(so)
        d.update(con=c["con"], chet=c["chet"], check_tay=c["check_tay"],
                 chua_check=c["chua_check"], khong_gia_tri=c["khong_gia_tri"],
                 sai_tang=c["sai_tang"])
        d["bu"] = sum(d.get(k, 0) for k, _, _ in KHOAN_BU)
        d["hao_hut"] = d["tho"] - d["nhan"]
        bang.append(d)

    bang.sort(key=lambda d: (d["tier"] is None, d["tier"] or 0, d["tab"]))
    return bang, rows, unmatched, file_kq, bang_trung(dups)


# --------------------------------------------------------------- link trung lap
def bang_trung(dups):
    """Bien ho so trung lap thanh danh sach phang, sap theo so lan lap giam dan.

    Moi dong: URL, so lan xuat hien tong cong, tab dat lan dau, cac tab lap lai,
    va trung trong cung mot tab hay trung cheo giua cac tab.
    """
    out = []
    for ho_so in dups.values():
        g_tier, g_tab = ho_so["goc"]
        lap = ho_so["lap"]
        tabs_lap = Counter(t for _tier, t, _u in lap)
        cheo = any(t != g_tab for t in tabs_lap)
        out.append({
            "url": ho_so["url"],
            "so_lan": len(lap) + 1,          # ke ca lan xuat hien dau tien
            "thua": len(lap),                # so luot bi loai = so link doi bu
            "tier_goc": g_tier,
            "tab_goc": g_tab,
            "tabs_lap": ", ".join("%s (x%d)" % (t, n) if n > 1 else t
                                  for t, n in tabs_lap.most_common()),
            "kieu": "Cheo tab" if cheo else "Trong cung tab",
            "tiers": sorted({g_tier} | {ti for ti, _t, _u in lap}),
        })
    out.sort(key=lambda d: (-d["so_lan"], d["tab_goc"], d["url"]))
    return out


def cong(bang, khoa):
    return sum(d.get(khoa, 0) or 0 for d in bang)


# ---------------------------------------------------------------------- console
def in_console(bang, file_kq, trung=(), out=sys.stderr):
    # Ten tab lay tu Google Sheet co dau tieng Viet. Console Windows mac dinh
    # la cp1252 nen print thang se no UnicodeEncodeError -> ep sang errors=replace.
    try:
        out.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    p = lambda *a: print(*a, file=out)
    w = 96
    p("=" * w)
    p("DOI SOAT NGUON BACKLINK VOI BEN CUNG CAP")
    p("=" * w)
    p("%-30s %6s %6s %6s %6s %6s %7s %6s"
      % ("Tab nguon", "Tho", "Trung", "Money", "Hong", "DomLoai", "Thuc nhan", "Chet"))
    p("-" * w)
    for d in bang:
        ten = d["tab"][:30]
        if d["bo_qua"]:
            p("%-30s %6d %s" % (ten, d["tho"], "[%s]" % d["bo_qua"]))
            continue
        p("%-30s %6d %6d %6d %6d %6d %7d %6d"
          % (ten, d["tho"], d["trung"], d["money_site"], d["url_hong"],
             d["domain_loai"], d["nhan"], d["chet"]))
    p("-" * w)
    p("%-30s %6d %6d %6d %6d %6d %7d %6d"
      % ("TONG", cong(bang, "tho"), cong(bang, "trung"), cong(bang, "money_site"),
         cong(bang, "url_hong"), cong(bang, "domain_loai"), cong(bang, "nhan"),
         cong(bang, "chet")))

    tho, nhan = cong(bang, "tho"), cong(bang, "nhan")
    p("")
    p("Ben cung cap dua       : %d dong link" % tho)
    p("Sau khi loc con        : %d link that (%.1f%%)"
      % (nhan, 100.0 * nhan / (tho or 1)))
    p("Hao hut                : %d link (%.1f%%)"
      % (tho - nhan, 100.0 * (tho - nhan) / (tho or 1)))
    p("So domain rieng biet   : %d" % cong(bang, "domain_rieng"))

    p("")
    p("DE NGHI BU LAI")
    p("-" * w)
    for khoa, nhan_khoa, vi_sao in KHOAN_BU:
        n = cong(bang, khoa)
        if n:
            p("  %-32s %5d   %s" % (nhan_khoa, n, vi_sao))
    p("  %-32s %5d" % ("=> TONG DE NGHI BU", cong(bang, "bu")))

    if trung:
        cheo = sum(1 for d in trung if d["kieu"] == "Cheo tab")
        p("")
        p("CHI TIET LINK TRUNG")
        p("-" * w)
        p("  %-32s %5d   %s" % ("So URL bi lap", len(trung),
                                "URL khac nhau, moi cai xuat hien tu 2 lan"))
        p("  %-32s %5d   %s" % ("So luot bi loai", sum(d["thua"] for d in trung),
                                "= so link de nghi bu vi trung"))
        p("  %-32s %5d" % ("Trong do trung cheo tab", cheo))
        p("  %-32s %5d" % ("Trung trong cung mot tab", len(trung) - cheo))
        p("")
        p("  Lap nhieu nhat:")
        for d in trung[:10]:
            p("    x%-3d %-26s %s" % (d["so_lan"], d["tab_goc"][:26], d["url"][:52]))
        if len(trung) > 10:
            p("    ... con %d URL nua - xem sheet 'Link trung' trong file xlsx"
              % (len(trung) - 10))

    ct, cc = cong(bang, "check_tay"), cong(bang, "chua_check")
    if ct or cc:
        p("")
        p("CHUA TINH VAO YEU CAU BU")
        if ct:
            p("  %-32s %5d   %s" % ("Chua ket luan duoc", ct,
                                    "tool bi chan, phai kiem tra tay truoc"))
        if cc:
            p("  %-32s %5d   %s" % ("Chua chay check", cc,
                                    "chay 'blcheck run' roi doi soat lai"))
    if file_kq:
        p("")
        p("Nguon ket qua check: %s" % ", ".join(file_kq))
    else:
        p("")
        p("CANH BAO: chua tim thay file ket qua check nao trong results/.")
        p("Cot 'Chet' dang bang 0 vi chua chay check, khong phai vi khong co link chet.")
    p("=" * w)


# ------------------------------------------------------------------------ xlsx
def write_xlsx(bang, path, cfg, rows=None, file_kq=(), kq=None, trung=()):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    HDR_FILL = PatternFill("solid", fgColor="305496")
    HDR_FONT = Font(color="FFFFFF", bold=True)
    TRU_FILL = PatternFill("solid", fgColor="FCE4D6")   # cot bi tru di
    NHAN_FILL = PatternFill("solid", fgColor="E2EFDA")  # cot thuc nhan
    BU_FILL = PatternFill("solid", fgColor="FFC7CE")    # cot de nghi bu
    TONG_FILL = PatternFill("solid", fgColor="D9D9D9")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    # ------------------------------------------------- sheet 1: bang doi soat
    ws = wb.active
    ws.title = "Doi soat"
    ws.append(["DOI SOAT NGUON BACKLINK VOI BEN CUNG CAP"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["Money site: %s   |   Ngay doi soat: %s"
               % (getattr(cfg, "money_domain", ""), date.today().isoformat())])
    ws.cell(row=2, column=1).font = Font(italic=True, color="7F7F7F")
    ws.append([])

    COLS = [
        ("tab",          "Tab / trang nguon", 32, None),
        ("tier",         "Tier", 6, None),
        ("tho",          "Ho dua (tho)", 12, None),
        ("trung",        "- Trung lap", 12, TRU_FILL),
        ("money_site",   "- Tro ve money site", 15, TRU_FILL),
        ("url_hong",     "- URL hong", 11, TRU_FILL),
        ("domain_loai",  "- Domain bi loai", 14, TRU_FILL),
        ("nhan",         "= Thuc nhan", 12, NHAN_FILL),
        ("domain_rieng", "Domain rieng", 12, None),
        ("con",          "Link con", 10, None),
        ("chet",         "Link chet", 10, None),
        ("khong_gia_tri", "Noindex", 10, None),
        ("sai_tang",     "Sai tang", 10, None),
        ("check_tay",    "Phai check tay", 13, None),
        ("bu",           "De nghi bu", 12, BU_FILL),
    ]
    hdr = ws.max_row + 1
    ws.append([c[1] for c in COLS])
    for i, (_, _, w, _f) in enumerate(COLS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
        c = ws.cell(row=hdr, column=i)
        c.fill, c.font = HDR_FILL, HDR_FONT
        c.alignment = Alignment(vertical="center", wrap_text=True, horizontal="center")
    ws.row_dimensions[hdr].height = 30

    for d in bang:
        if d["bo_qua"]:
            ws.append([d["tab"], "-", d["tho"], "", "", "", "", 0, d["bo_qua"]])
            ws.cell(row=ws.max_row, column=1).font = Font(color="808080", italic=True)
            ws.cell(row=ws.max_row, column=9).font = Font(color="808080", italic=True)
            continue
        ws.append([d.get(k, "") for k, _, _, _ in COLS])
        rn = ws.max_row
        for i, (_k, _l, _w, fill) in enumerate(COLS, 1):
            if fill:
                ws.cell(row=rn, column=i).fill = fill
        ws.cell(row=rn, column=8).font = Font(bold=True)
        if d["bu"]:
            ws.cell(row=rn, column=13).font = Font(bold=True, color="9C0006")

    ws.append(["TONG", ""] + [cong(bang, k) for k, _, _, _ in COLS[2:]])
    rn = ws.max_row
    for i in range(1, len(COLS) + 1):
        ws.cell(row=rn, column=i).fill = TONG_FILL
        ws.cell(row=rn, column=i).font = Font(bold=True)
    ws.freeze_panes = "A%d" % (hdr + 1)

    # ------------------------------------------------- khoi ket luan + de nghi bu
    tho, nhan = cong(bang, "tho"), cong(bang, "nhan")
    ws.append([])
    ws.append(["KET LUAN DOI SOAT"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=13)
    for ten_o, gia_tri in (
        ("Ben cung cap dua", "%d dong link" % tho),
        ("Sau khi loc con lai", "%d link that (%.1f%%)"
         % (nhan, 100.0 * nhan / (tho or 1))),
        ("Hao hut", "%d link (%.1f%%)"
         % (tho - nhan, 100.0 * (tho - nhan) / (tho or 1))),
        ("So domain rieng biet", "%d" % cong(bang, "domain_rieng")),
        ("So URL bi lap", "%d URL, loai di %d luot"
         % (len(trung), sum(d["thua"] for d in trung))),
    ):
        ws.append([ten_o, "", gia_tri])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)

    ws.append([])
    ws.append(["DE NGHI BU LAI"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=13)
    ws.append(["Khoan", "So luong", "Vi sao khong tinh la da giao du"])
    for c in range(1, 4):
        ws.cell(row=ws.max_row, column=c).fill = HDR_FILL
        ws.cell(row=ws.max_row, column=c).font = HDR_FONT
    for khoa, ten_khoan, vi_sao in KHOAN_BU:
        ws.append([ten_khoan, cong(bang, khoa), vi_sao])
        for c in range(1, 4):
            ws.cell(row=ws.max_row, column=c).fill = BU_FILL
    ws.append(["TONG DE NGHI BU", cong(bang, "bu"), ""])
    for c in range(1, 4):
        ws.cell(row=ws.max_row, column=c).fill = BU_FILL
        ws.cell(row=ws.max_row, column=c).font = Font(bold=True, size=12, color="9C0006")

    ct, cc = cong(bang, "check_tay"), cong(bang, "chua_check")
    if ct or cc:
        ws.append([])
        ws.append(["CHUA TINH VAO YEU CAU BU"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
        if ct:
            ws.append(["Chua ket luan duoc", ct,
                       "Tool bi chan bot / captcha nen chua co bang chung. "
                       "Kiem tra tay xong moi doi bu."])
        if cc:
            ws.append(["Chua chay check", cc,
                       "Chay lenh run roi doi soat lai."])

    # ------------------------------------------------- sheet 2: link trung
    if trung:
        _sheet_trung(wb, trung)

    # ------------------------------------------------- sheet 3: link chet
    if rows is not None and kq is not None:
        _sheet_chet(wb, rows, kq)

    wb.save(path)
    return path


def _sheet_trung(wb, trung):
    """Danh sach URL bi giao trung - phan gui kem khi de nghi bu."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    HDR_FILL = PatternFill("solid", fgColor="305496")
    HDR_FONT = Font(color="FFFFFF", bold=True)
    CAM = PatternFill("solid", fgColor="FCE4D6")
    DO = PatternFill("solid", fgColor="FFC7CE")

    ws = wb.create_sheet("Link trung")
    ws.append(["DANH SACH URL BI GIAO TRUNG"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append(["Cot 'Thua' la so luot bi loai - cong lai chinh la so link de nghi bu "
               "vi trung. URL lap nhieu nhat nam tren cung."])
    ws.cell(row=2, column=1).font = Font(italic=True, color="7F7F7F")
    ws.append([])

    COLS = [("URL bi lap", 64), ("So lan", 8), ("Thua", 7), ("Kieu trung", 16),
            ("Tier", 8), ("Tab dat lan dau", 28), ("Cac tab lap lai", 40)]
    hdr = ws.max_row + 1
    ws.append([c[0] for c in COLS])
    for i, (_, w) in enumerate(COLS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
        c = ws.cell(row=hdr, column=i)
        c.fill, c.font = HDR_FILL, HDR_FONT
        c.alignment = Alignment(vertical="center", wrap_text=True, horizontal="center")
    ws.row_dimensions[hdr].height = 26

    for d in trung:
        ws.append([d["url"], d["so_lan"], d["thua"], d["kieu"],
                   ", ".join(str(t) for t in d["tiers"]),
                   d["tab_goc"], d["tabs_lap"]])
        rn = ws.max_row
        for i in range(1, len(COLS) + 1):
            c = ws.cell(row=rn, column=i)
            c.fill = DO if d["so_lan"] > 2 else CAM
            c.alignment = Alignment(vertical="top", wrap_text=(i == 7))
        ws.cell(row=rn, column=3).font = Font(bold=True, color="9C0006")
        if len(d["url"]) < 250:
            c = ws.cell(row=rn, column=1)
            c.hyperlink = d["url"]
            c.font = Font(color="0563C1", underline="single")

    ws.append(["TONG", sum(d["so_lan"] for d in trung),
               sum(d["thua"] for d in trung), "", "", "", ""])
    for i in range(1, len(COLS) + 1):
        ws.cell(row=ws.max_row, column=i).font = Font(bold=True)
        ws.cell(row=ws.max_row, column=i).fill = PatternFill("solid", fgColor="D9D9D9")

    ws.freeze_panes = "A%d" % (hdr + 1)
    ws.auto_filter.ref = "A%d:%s%d" % (hdr, get_column_letter(len(COLS)), ws.max_row - 1)
    return ws


def _sheet_chet(wb, rows, kq):
    """Danh sach tung URL da chet - phan gui kem khi bao lai ben cung cap."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    HDR_FILL = PatternFill("solid", fgColor="305496")
    HDR_FONT = Font(color="FFFFFF", bold=True)
    BU_FILL = PatternFill("solid", fgColor="FFC7CE")

    NOINDEX_FILL = PatternFill("solid", fgColor="FFE699")
    SAI_TANG_FILL = PatternFill("solid", fgColor="D9E1F2")

    ws = wb.create_sheet("Link chet - gui ho")
    ws.append(["DANH SACH LINK KHONG DUNG DUOC - GUI KEM KHI DE NGHI BU"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append(["Gom ba nhom: link DA CHET (do); link con nhung trang NOINDEX nen "
               "khong truyen gia tri (vang); va link song nhung TRO SAI TANG so "
               "voi tang ho khai giao (xanh). Moi dong deu co bang chung."])
    ws.cell(row=2, column=1).font = Font(italic=True, color="7F7F7F")
    ws.append([])

    COLS = [("Tier", 6), ("Tab nguon", 26), ("URL co van de", 62),
            ("Nhom", 14), ("Ma loi", 22), ("Chan doan", 60), ("HTTP", 7)]
    hdr = ws.max_row + 1
    ws.append([c[0] for c in COLS])
    for i, (_, w) in enumerate(COLS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
        c = ws.cell(row=hdr, column=i)
        c.fill, c.font = HDR_FILL, HDR_FONT
        c.alignment = Alignment(vertical="center", wrap_text=True)

    n = 0
    for r in rows:
        k = kq.get(U.normalize(r["source_url"]))
        if not k:
            continue
        chet = _ket_luan(k) == D.V_MAT
        noindex = not chet and _khong_gia_tri(k)
        # Cung thu tu uu tien voi luc dem o build(): mot dong chi thuoc mot nhom.
        sai_tang = not chet and not noindex and _sai_tang(k)
        if not (chet or noindex or sai_tang):
            continue
        nhom = "Da chet" if chet else ("Noindex" if noindex else "Sai tang")
        ws.append([r["tier"], r["sheet"], r["source_url"], nhom,
                   k.get("diag_code", ""), k.get("chan_doan", ""),
                   k.get("http_code", "")])
        rn = ws.max_row
        to = BU_FILL if chet else (NOINDEX_FILL if noindex else SAI_TANG_FILL)
        for i in range(1, len(COLS) + 1):
            ws.cell(row=rn, column=i).fill = to
            ws.cell(row=rn, column=i).alignment = Alignment(
                vertical="top", wrap_text=(i == 6))
        if len(r["source_url"]) < 250:
            c = ws.cell(row=rn, column=3)
            c.hyperlink = r["source_url"]
            c.font = Font(color="0563C1", underline="single")
        n += 1

    if not n:
        ws.append(["", "", "Khong co link nao chet hoac noindex.", "", "", "", ""])
        ws.cell(row=ws.max_row, column=3).font = Font(color="006100", bold=True)
    else:
        ws.freeze_panes = "A%d" % (hdr + 1)
        ws.auto_filter.ref = "A%d:%s%d" % (hdr, get_column_letter(len(COLS)),
                                           ws.max_row)
    return ws


def main():
    ap = argparse.ArgumentParser(
        description="Doi soat nguon backlink voi ben cung cap")
    ap.add_argument("-c", "--config", required=True)
    ap.add_argument("--url", default="", help="ghi de source.url trong config")
    ap.add_argument("-o", "--output", default="", help="duong dan file xlsx")
    ap.add_argument("--results-dir", default="", help="thu muc chua ket qua check")
    args = ap.parse_args()

    cfg = bl_config.load(args.config)
    thu_muc = args.results_dir or None
    bang, rows, unmatched, file_kq, trung = build(cfg, args.url, thu_muc)
    in_console(bang, file_kq, trung)

    kq, _ = doc_ket_qua(cfg, thu_muc)
    out = args.output or str(Path(cfg.output.get("dir", "results"))
                             / ("%s_%s_doi-soat.xlsx"
                                % (date.today().isoformat(), cfg.site_name)))
    p = write_xlsx(bang, out, cfg, rows, file_kq, kq, trung)
    print("\nDa ghi: %s" % p, file=sys.stderr)


if __name__ == "__main__":
    main()
