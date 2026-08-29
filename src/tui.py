"""Giao dien terminal: banner, panel, bang mau - dung rich."""

import sys

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

__app_name__ = "tool check backlink"
__version__ = "1.0.0"
__author__ = "luomnv04.mima@gmail.com"
__description__ = "Backlink pyramid checker"

# Ten tab lay tu Google Sheet co dau tieng Viet, con banner dung ky tu ve khung.
# Console Windows mac dinh la cp1252 -> ghi thang se no UnicodeEncodeError va
# lam chet ca lenh. Ep sang UTF-8 truoc khi rich cham vao stdout/stderr.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

console = Console()

# Icon ASCII - hai mat xich long nhau
ICON = """
              ▄▄▄▄▄▄▄▄▄▄
          ▄████████████████▄▄
       ▄██████████████████████▄
     ▄██▀▄██████████████▀▀██████▄
    ███▄████ ███████████  ▀███████▄
  ▄████████   ▀████████    ▀███████▄
  █████████     ██████       ███████▄
 █████████       ▀███    ▄    ███████
 █████████    ▄    █▀   ██▄    ▀█████
 ████████▀   ██▄       ███▀     ▀████
 ████████    ████▄    █▀   ▄▄    ▀███
 ███████▀    █████▄  ▄███████▄ ▄▄▄███
  ██████    ████████▄███████████████▀
  ▀█████    ███████████████████████▀
    ███▄▄▄▄███████████████████████▀
     ▀██████████████████████████▀
       ▀██████████████████████▀
          ▀████████████████▀▀
              ▀▀▀▀▀▀▀▀▀▀
"""

# mau theo muc do nghiem trong, khop voi diagnose.SEV_*
SEV_STYLE = {
    "CHET": "bold red",
    "NANG": "dark_orange",
    "CANH BAO": "yellow",
    "GHI CHU": "cyan",
    "TOT": "green",
}
STATUS_STYLE = {
    "FOUND": "green",
    "NOT_FOUND": "yellow",
    "PAGE_ERROR": "red",
}


def render_banner() -> Panel:
    icon = Text(ICON, style="bold white")

    info = Table.grid(padding=(0, 2))
    info.add_column(justify="left")
    info.add_row(Text(__app_name__, style="bold white"))
    info.add_row(
        Text("v%s " % __version__, style="dim white")
        + Text("· Kiem tra backlink kim tu thap", style="dim white")
    )
    info.add_row(Text("by %s" % __author__, style="dim"))

    body = Table.grid(padding=(0, 1))
    body.add_column()
    body.add_column()
    body.add_row(icon, Align.left(info, vertical="middle"))

    return Panel(body, border_style="white", padding=(0, 2), expand=False)


def show_banner():
    console.print()
    console.print(render_banner())
    console.print()


def show_help_hint():
    hint = Table.grid(padding=(0, 2))
    hint.add_column(style="bold cyan", justify="left")
    hint.add_column(style="white")
    hint.add_row("blcheck run", "Chay tron goi: nap du lieu → check moi tier → bao cao")
    hint.add_row("blcheck run --tier 1", "Chi chay mot tier")
    hint.add_row("blcheck ingest", "Chi nap + lam sach du lieu tu Google Sheet")
    hint.add_row("blcheck check --tier 2", "Chi check, khong nap lai du lieu")
    hint.add_row("blcheck diff <cu> <moi>", "So sanh hai lan chay")
    hint.add_row("blcheck --help", "Xem tat ca lenh")
    console.print(Panel(hint, title="[dim]Lenh[/dim]", border_style="dim", expand=False))
    console.print()


def config_panel(cfg, source_desc, tiers_to_run, limit=None):
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column(style="white")
    t.add_row("Site", "%s  [dim](%s)[/dim]" % (cfg.site_name, cfg.money_domain))
    t.add_row("Nguon du lieu", source_desc)
    t.add_row("File sach", str(cfg.master_csv))
    t.add_row("Tier se chay", ", ".join(str(x) for x in tiers_to_run) or "(khong)")
    t.add_row("Song song", "%s request  ·  nghi %ss/domain  ·  timeout %ss"
              % (cfg.network["concurrency"], cfg.network["per_domain_delay"],
                 cfg.network["timeout"]))
    if limit:
        t.add_row("Gioi han", "[yellow]%d link dau moi tier (che do thu)[/yellow]" % limit)
    t.add_row("Ket qua", "%s/  (csv + xlsx to mau)" % cfg.output["dir"])
    return Panel(t, title="[cyan]Cau hinh[/cyan]", border_style="cyan", expand=False)


def ingest_table(per_sheet, unmatched, stats):
    t = Table(box=None, pad_edge=False)
    t.add_column("Tab nguon", style="white")
    t.add_column("Tier", justify="center", style="cyan")
    t.add_column("Link", justify="right", style="bold")
    t.add_column("", style="dim")
    for name, tier, n, note in per_sheet:
        t.add_row(name, str(tier) if tier else "[red]-[/red]", str(n), note)
    for name in unmatched:
        t.add_row(name, "[red]?[/red]", "0", "[red]khong khop tier nao[/red]")
    return t


def tier_summary_table(results_by_tier, cfg):
    t = Table(title=None, header_style="bold white on grey23")
    t.add_column("Tier", justify="center")
    t.add_column("Ten", style="dim")
    t.add_column("Tong", justify="right")
    t.add_column("Song", justify="right", style="green")
    t.add_column("Mat link", justify="right", style="yellow")
    t.add_column("Loi trang", justify="right", style="red")
    t.add_column("CHET", justify="right", style="bold red")
    t.add_column("NANG", justify="right", style="dark_orange")
    for tier in sorted(results_by_tier, key=lambda x: int(x)):
        rs = results_by_tier[tier]
        lab = cfg.tiers[int(tier)].label if int(tier) in cfg.tiers else ""
        c = lambda k: sum(1 for r in rs if r.status == k)
        m = lambda k: sum(1 for r in rs if r.muc_do == k)
        t.add_row(str(tier), lab[:34], str(len(rs)), str(c("FOUND")),
                  str(c("NOT_FOUND")), str(c("PAGE_ERROR")),
                  str(m("CHET")), str(m("NANG")))
    return t


def doisoat_table(bang):
    """Bang doi soat voi ben cung cap: ho dua bao nhieu -> ta nhan bao nhieu.

    Cot nao toan so 0 thi an di cho bang do chat - phan lon du an chi dinh
    mot vai loai hao hut chu khong dinh het.
    """
    import doisoat as DS

    c = lambda k: DS.cong(bang, k)
    # (khoa, tieu de, do rong, mau) - chi hien khi co so lieu
    tuy_chon = [("trung", "Trung", 5, "dark_orange"),
                ("money_site", "Money", 5, "dark_orange"),
                ("url_hong", "Hong", 4, "dark_orange"),
                ("domain_loai", "Loai", 4, "dark_orange")]
    hien = [x for x in tuy_chon if c(x[0])]

    t = Table(header_style="bold white on grey23")
    t.add_column("Tab / trang nguon", style="white", width=26,
                 no_wrap=True, overflow="ellipsis")
    t.add_column("T", justify="center", style="cyan", width=3)
    t.add_column("Ho dua", justify="right", width=6)
    for _k, ten, w, st in hien:
        t.add_column(ten, justify="right", style=st, width=w)
    t.add_column("Nhan", justify="right", style="bold green", width=6)
    t.add_column("Chet", justify="right", style="red", width=4)
    t.add_column("Doi bu", justify="right", style="bold red", width=6)

    canh = lambda n, st: ("[%s]%d[/%s]" % (st, n, st)) if n else "[dim]0[/dim]"
    for d in bang:
        if d["bo_qua"]:
            t.add_row("[dim]%s[/dim]" % d["tab"], "[dim]-[/dim]", str(d["tho"]),
                      *([""] * len(hien)), "", "", "[dim]bo qua[/dim]")
            continue
        t.add_row(d["tab"], str(d["tier"]), str(d["tho"]),
                  *[canh(d[k], st) for k, _t, _w, st in hien],
                  str(d["nhan"]), canh(d["chet"], "red"),
                  canh(d["bu"], "bold red"))

    b = lambda n: "[bold]%d[/bold]" % n
    t.add_section()
    t.add_row("[bold]TONG[/bold]", "", b(c("tho")),
              *[b(c(k)) for k, _t, _w, _s in hien],
              b(c("nhan")), b(c("chet")), "[bold red]%d[/bold red]" % c("bu"))
    return t


def doisoat_panel(bang, trung=()):
    """Khoi ket luan doi soat: de nghi bu bao nhieu link, vi sao."""
    import doisoat as DS

    c = lambda k: DS.cong(bang, k)
    tho, nhan = c("tho"), c("nhan")

    g = Table.grid(padding=(0, 2))
    g.add_column(style="dim", justify="right", width=24)
    g.add_column(justify="right", width=7)
    g.add_column()
    g.add_row("Ben cung cap dua", "[bold]%d[/bold]" % tho, "[dim]dong link tho[/dim]")
    g.add_row("Sau khi loc con", "[bold green]%d[/bold green]" % nhan,
              "[dim]link that (%.1f%%)[/dim]" % (100.0 * nhan / (tho or 1)))
    g.add_row("Hao hut", "[bold dark_orange]%d[/bold dark_orange]" % (tho - nhan),
              "[dim]%.1f%%[/dim]" % (100.0 * (tho - nhan) / (tho or 1)))
    g.add_row("So domain rieng biet", "%d" % c("domain_rieng"),
              "[dim]bao nhieu site khac nhau that su[/dim]")
    if trung:
        g.add_row("So URL bi lap", "[dark_orange]%d[/dark_orange]" % len(trung),
                  "[dim]URL khac nhau, loai di %d luot[/dim]"
                  % sum(d["thua"] for d in trung))
    g.add_row("", "", "")
    g.add_row("[bold]DE NGHI BU LAI[/bold]", "", "")
    for khoa, ten, vi_sao in DS.KHOAN_BU:
        n = c(khoa)
        if n:
            g.add_row(ten, "[red]%d[/red]" % n, "[dim]%s[/dim]" % vi_sao)
    g.add_row("[bold]=> TONG DE NGHI BU[/bold]",
              "[bold red]%d[/bold red]" % c("bu"), "")
    ct, cc = c("check_tay"), c("chua_check")
    if ct or cc:
        g.add_row("", "", "")
        if ct:
            g.add_row("[dim]Chua ket luan duoc[/dim]", "[yellow]%d[/yellow]" % ct,
                      "[dim]chua co bang chung - kiem tra tay truoc khi doi bu[/dim]")
        if cc:
            g.add_row("[dim]Chua chay check[/dim]", "[yellow]%d[/yellow]" % cc,
                      "[dim]chay 'blcheck run' roi doi soat lai[/dim]")
    return Panel(g, title="[bold]Ket luan doi soat[/bold]",
                 border_style="magenta", expand=False)


def trung_cap_table(trung):
    """Trung lap giua cap tab nao voi cap tab nao - nhin ra ngay tab bi copy.

    Day moi la con so de mang di noi chuyen: "tab A that ra la ban sao cua tab B"
    manh hon nhieu so voi mot danh sach 400 URL le te.
    """
    from collections import Counter

    cap = Counter()
    for d in trung:
        for phan in d["tabs_lap"].split(", "):
            ten = phan.rsplit(" (x", 1)[0]
            cap[(d["tab_goc"], ten)] += d["thua"] if len(d["tabs_lap"]) else 1

    t = Table(header_style="bold white on grey23",
              title="[bold]Trung lap giua cac tab[/bold]", title_justify="left")
    t.add_column("Tab dat lan dau", width=26, no_wrap=True, overflow="ellipsis")
    t.add_column("Tab lap lai", width=26, no_wrap=True, overflow="ellipsis")
    t.add_column("So URL", justify="right", style="bold red", width=6)
    for (goc, lap), n in cap.most_common(10):
        mau = "yellow" if goc != lap else "dim"
        t.add_row("[%s]%s[/%s]" % (mau, goc, mau),
                  "[%s]%s[/%s]" % (mau, lap, mau), str(n))
    return t


def trung_table(trung, top=10):
    """Vai URL bi giao trung, de nguoi dung thay mat mui du lieu that."""
    t = Table(header_style="bold white on grey23",
              title="[bold]Vi du URL bi giao trung[/bold]", title_justify="left")
    t.add_column("Lan", justify="right", style="bold dark_orange", width=4)
    t.add_column("Tab dat lan dau", width=22, no_wrap=True, overflow="ellipsis")
    t.add_column("URL", overflow="ellipsis", no_wrap=True)

    for d in trung[:top]:
        t.add_row("x%d" % d["so_lan"], d["tab_goc"], d["url"])
    if len(trung) > top:
        t.add_section()
        t.add_row("", "[dim]... con %d URL[/dim]" % (len(trung) - top),
                  "[dim]xem sheet 'Link trung' trong file xlsx[/dim]")
    return t


def verdict_panel(results):
    """Khoi 3 con so nguoi dung can nhat: con / mat / phai check tay."""
    import diagnose as D

    d = D.dem_ket_luan(results)
    tong = d["TONG"] or 1
    pc = lambda n: 100.0 * n / tong

    t = Table.grid(padding=(0, 2))
    t.add_column(justify="right", width=16)
    t.add_column(justify="right", width=6)
    t.add_column(justify="right", width=7, style="dim")
    t.add_column()
    t.add_row("[bold green]Link con[/bold green]", "[bold green]%d[/bold green]"
              % d[D.V_SONG], "%.1f%%" % pc(d[D.V_SONG]),
              "[dim]khong can mo tay - trong do %d link hoan hao[/dim]" % d["HOAN_HAO"])
    t.add_row("[bold red]Link mat[/bold red]", "[bold red]%d[/bold red]"
              % d[D.V_MAT], "%.1f%%" % pc(d[D.V_MAT]),
              "[dim]khong can mo tay - thay bang nguon moi[/dim]")
    t.add_row("[bold yellow]Phai check tay[/bold yellow]",
              "[bold yellow]%d[/bold yellow]" % d[D.V_CHECK],
              "%.1f%%" % pc(d[D.V_CHECK]),
              "[dim]tool chua doc duoc - CHUA phai la mat link[/dim]")
    if d[D.V_CHECK]:
        t.add_row("", "", "", "")
        t.add_row("[dim]› chay lai tool[/dim]", "%d" % d[D.X_TOOL], "",
                  "[dim]may lam - cai Playwright / bat --js / cho roi chay lai[/dim]")
        t.add_row("[dim]› mo trinh duyet[/dim]", "%d" % d[D.X_NGUOI], "",
                  "[dim]nguoi lam - xem sheet 'Can check tay' trong file xlsx[/dim]")
    return Panel(t, title="[bold]Chot lai[/bold]", border_style="cyan", expand=False)


def manual_check_list(results, limit=12):
    """Nhung link phai mo trinh duyet, gom theo ma loi."""
    from collections import defaultdict
    import diagnose as D

    need = [r for r in results
            if (getattr(r, "ket_luan", "") == D.V_CHECK
                and getattr(r, "cach_xu_ly", "") == D.X_NGUOI)]
    if not need:
        return None
    by_code = defaultdict(list)
    for r in need:
        by_code[r.diag_code].append(r)

    t = Table(box=None, pad_edge=False)
    t.add_column("Ma loi", style="yellow", width=22)
    t.add_column("SL", justify="right", width=4)
    t.add_column("Lam gi de biet chac", style="dim")
    for code, rs in sorted(by_code.items(), key=lambda kv: -len(kv[1])):
        t.add_row(code, str(len(rs)), D.HUONG_DAN_CHECK.get(code, "")[:66])
    t.add_row("", "", "")
    t.add_row("[dim]URL cu the[/dim]", "", "[dim]sheet 'Can check tay' trong file xlsx[/dim]")
    return t


def diag_table(results, top=12):
    from collections import Counter
    import diagnose as D

    counts = Counter(r.diag_code for r in results if r.diag_code)
    rows = []
    for code, n in counts.items():
        if code not in D.CATALOG:
            continue
        sev = min((int(r.severity) for r in results
                   if r.diag_code == code and r.severity), default=3)
        rows.append((sev, -n, code, n, D.CATALOG[code][2]))
    rows.sort()

    t = Table(header_style="bold white on grey23")
    t.add_column("Muc do", justify="center")
    t.add_column("Ma loi")
    t.add_column("SL", justify="right")
    t.add_column("Viec can lam", style="dim")
    for sev, _, code, n, todo in rows[:top]:
        lab = D.SEV_LABEL[sev]
        st = SEV_STYLE.get(lab, "white")
        t.add_row("[%s]%s[/%s]" % (st, lab, st), "[%s]%s[/%s]" % (st, code, st),
                  str(n), todo[:64])
    if len(rows) > top:
        t.add_row("[dim]...[/dim]", "[dim]con %d ma loi nua[/dim]" % (len(rows) - top),
                  "", "[dim]xem file xlsx[/dim]")
    return t


def critical_list(results, limit=15):
    """Danh sach link nghiem trong nhat, de xu ly ngay."""
    bad = sorted([r for r in results if r.severity and int(r.severity) <= 2],
                 key=lambda r: (int(r.severity), int(r.tier) if str(r.tier).isdigit() else 9))
    if not bad:
        return None
    t = Table(box=None, pad_edge=False)
    t.add_column("", justify="center", width=9)
    t.add_column("T", justify="center", width=3, style="cyan")
    t.add_column("URL")
    t.add_column("Ma loi", style="dim")
    for r in bad[:limit]:
        st = SEV_STYLE.get(r.muc_do, "white")
        t.add_row("[%s]%s[/%s]" % (st, r.muc_do, st), str(r.tier),
                  r.source_url[:70], r.diag_code)
    if len(bad) > limit:
        t.add_row("", "", "[dim]... con %d link nua trong file xlsx[/dim]"
                  % (len(bad) - limit), "")
    return t


def ok_panel(title, body):
    return Panel(body, title="[green]✓ %s[/green]" % title,
                 border_style="green", expand=False)


def err_panel(title, body):
    return Panel(str(body), title="[red]✗ %s[/red]" % title,
                 border_style="red", expand=False)


def warn_panel(title, body):
    return Panel(body, title="[yellow]⚠ %s[/yellow]" % title,
                 border_style="yellow", expand=False)
