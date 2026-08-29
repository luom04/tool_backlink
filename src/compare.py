"""
So sanh hai lan chay de biet link nao vua mat, vua khoi phuc, vua xau di.

Chay:
    python src/compare.py results/2026-08-11_site_tier1.csv results/2026-08-25_site_tier1.csv
    python src/compare.py cu.csv moi.csv -o results/thay-doi.csv

Doc duoc ca file ket qua cu (khong co cot chan doan) lan file moi.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import diagnose as D

RANK = {"FOUND": 0, "NOT_FOUND": 1, "PAGE_ERROR": 2}


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {r["source_url"]: r for r in csv.DictReader(f) if r.get("source_url")}


def sev_of(row):
    try:
        return int(row.get("severity") or 0)
    except ValueError:
        return 0


def main():
    ap = argparse.ArgumentParser(description="So sanh 2 lan chay backlink checker")
    ap.add_argument("old_csv", help="ket qua lan chay truoc")
    ap.add_argument("new_csv", help="ket qua lan chay moi")
    ap.add_argument("-o", "--output", help="luu danh sach thay doi ra CSV")
    args = ap.parse_args()

    old, new = load(args.old_csv), load(args.new_csv)

    changes = []
    for url, n in new.items():
        o = old.get(url)
        if o is None:
            changes.append(("MOI_THEM", url, "-", n["status"], n))
            continue
        if o["status"] != n["status"]:
            worse = RANK.get(n["status"], 9) > RANK.get(o["status"], 9)
            changes.append(("MAT_LINK" if worse else "KHOI_PHUC",
                            url, o["status"], n["status"], n))
        elif o.get("diag_code") and n.get("diag_code") and o["diag_code"] != n["diag_code"]:
            changes.append(("DOI_LOI", url, o["diag_code"], n["diag_code"], n))

    removed = [u for u in old if u not in new]
    lost = [c for c in changes if c[0] == "MAT_LINK"]
    back = [c for c in changes if c[0] == "KHOI_PHUC"]
    added = [c for c in changes if c[0] == "MOI_THEM"]
    shifted = [c for c in changes if c[0] == "DOI_LOI"]

    print("Lan cu : %s  (%d link)" % (args.old_csv, len(old)))
    print("Lan moi: %s  (%d link)" % (args.new_csv, len(new)))
    print("=" * 66)
    print("VUA MAT              : %d" % len(lost))
    print("VUA KHOI PHUC        : %d" % len(back))
    print("DOI KIEU LOI         : %d" % len(shifted))
    print("MOI THEM             : %d" % len(added))
    print("BI XOA KHOI DANH SACH: %d" % len(removed))

    if lost:
        print("\n--- LINK VUA MAT (uu tien xu ly, tier nho truoc) ---")
        for _, url, o, n, row in sorted(lost, key=lambda c: (sev_of(c[4]),
                                                            c[4].get("tier", ""))):
            print("  T%s [%s -> %s] %s  %s"
                  % (row.get("tier", "?"), o, n, row.get("diag_code", ""), url))
            todo = row.get("viec_can_lam") or D.CATALOG.get(row.get("diag_code", ""), ("", "", ""))[2]
            if todo:
                print("        -> %s" % todo)

    if back:
        print("\n--- LINK VUA KHOI PHUC ---")
        for _, url, o, n, row in back:
            print("  T%s [%s -> %s] %s" % (row.get("tier", "?"), o, n, url))

    if shifted:
        print("\n--- VAN FOUND/NOT_FOUND NHUNG DOI KIEU LOI ---")
        for _, url, o, n, row in shifted[:40]:
            print("  T%s [%s -> %s] %s" % (row.get("tier", "?"), o, n, url))
        if len(shifted) > 40:
            print("  ... con %d dong nua, xem file -o" % (len(shifted) - 40))

    if args.output and changes:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["loai_thay_doi", "tier", "source_url", "truoc", "sau",
                        "muc_do", "diag_code", "chan_doan", "viec_can_lam", "http_code"])
            for kind, url, o, n, row in changes:
                w.writerow([kind, row.get("tier", ""), url, o, n,
                            row.get("muc_do", ""), row.get("diag_code", ""),
                            row.get("chan_doan", ""), row.get("viec_can_lam", ""),
                            row.get("http_code", "")])
        print("\nDa luu: %s" % args.output)

    if not changes and not removed:
        print("\nKhong co thay doi nao.")


if __name__ == "__main__":
    main()
