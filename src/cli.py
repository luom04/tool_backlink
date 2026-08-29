"""
blcheck - CLI mot lenh chay tron goi kiem tra backlink.

    python src/cli.py run -c config/checkbacklink.yaml

Chay lan luot: nap du lieu tu Google Sheet -> check tung tier theo thu tu uu
tien -> xuat CSV + XLSX to mau -> so sanh voi lan chay truoc -> in bao cao.
"""

import asyncio
import shlex
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import typer
from rich.panel import Panel
from rich.progress import (BarColumn, MofNCompleteColumn, Progress, SpinnerColumn,
                           TextColumn, TimeElapsedColumn)
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))
import bl_config
import checker
import ingest as ingest_mod
import report as report_mod
import tui
from tui import console, __app_name__, __version__

app = typer.Typer(name=__app_name__, help="Kiem tra backlink kim tu thap.",
                  add_completion=False, no_args_is_help=False,
                  invoke_without_command=True)

DEFAULT_CONFIG = "config/checkbacklink.yaml"


@app.callback()
def main(ctx: typer.Context):
    """Go `blcheck` khong kem lenh -> vao che do tuong tac."""
    if ctx.invoked_subcommand is None:
        if sys.stdin.isatty():
            run_repl()
        else:
            tui.show_banner()
            tui.show_help_hint()


def run_repl():
    tui.show_banner()
    console.print(
        "[dim]Che do tuong tac — go lenh roi Enter (vd: "
        "[cyan]run[/cyan], [cyan]ingest[/cyan], [cyan]help[/cyan]). "
        "Thoat: [cyan]exit[/cyan] hoac Ctrl-D.[/dim]\n"
    )
    try:
        import readline  # noqa: F401
    except ImportError:
        pass
    cli = typer.main.get_command(app)
    while True:
        try:
            line = console.input("[bold cyan]blcheck ❯[/bold cyan] ").strip()
        except EOFError:
            console.print()
            break
        except KeyboardInterrupt:
            console.print()
            continue
        if not line:
            continue
        if line in ("exit", "quit", "q"):
            break
        if line in ("help", "?", "h"):
            line = "--help"
        try:
            cli(args=shlex.split(line), prog_name=__app_name__, standalone_mode=False)
        except SystemExit:
            pass
        except KeyboardInterrupt:
            console.print("\n[yellow]Da huy lenh.[/yellow]")
        except Exception as e:
            console.print("[red]Loi:[/red] %s" % e)
        console.print()


def _load(config_path):
    try:
        return bl_config.load(config_path)
    except bl_config.ConfigError as e:
        console.print(tui.err_panel("Loi cau hinh", e))
        raise typer.Exit(code=1)


def _playwright_available():
    try:
        import playwright.async_api  # noqa: F401
        return True
    except ImportError:
        return False


def _source_desc(cfg):
    if cfg.source_url:
        kind = ingest_mod.detect_source(cfg.source_url)
        name = {"google_sheet": "Google Sheet", "google_doc": "Google Docs"}.get(kind, kind)
        return "%s  [dim]%s[/dim]" % (name, cfg.source_url[:58] + "...")
    return "File trong may  [dim]%s[/dim]" % (cfg.source_file or cfg.master_csv)


# --------------------------------------------------------------- buoc nap lieu
def _do_ingest(cfg, dry_run=False, url=""):
    console.print("[bold]› Buoc 1 — Nap va lam sach du lieu[/bold]")
    per_sheet = []

    with console.status("[cyan]Dang tai nguon du lieu...[/cyan]", spinner="dots"):
        try:
            rows, stats, unmatched, dups = ingest_mod.build(cfg, url, verbose=False)
        except SystemExit as e:
            console.print(tui.err_panel("Khong tai duoc nguon du lieu", e))
            raise typer.Exit(code=1)

    by = defaultdict(int)
    tier_of = {}
    for r in rows:
        by[r["sheet"]] += 1
        tier_of[r["sheet"]] = r["tier"]
    for sheet in by:
        per_sheet.append((sheet, tier_of[sheet], by[sheet], ""))
    per_sheet.sort(key=lambda x: (x[1], x[0]))

    console.print(tui.ingest_table(per_sheet, unmatched, stats))

    line = []
    for k, lab in (("trung_lap", "trung lap"), ("url_hong", "URL hong"),
                   ("tu_tro_ve_money_site", "tu tro ve money site"),
                   ("domain_bi_loai", "domain bi loai")):
        if stats[k]:
            line.append("%s: %d" % (lab, stats[k]))
    console.print("  [dim]Da loai — %s[/dim]" % (", ".join(line) if line else "khong co"))

    if unmatched:
        console.print(tui.warn_panel(
            "%d tab khong khop tier nao" % len(unmatched),
            "\n".join("  · %s" % s for s in unmatched)
            + "\n\n[dim]Them tu khoa vao 'tiers.<N>.match' trong config.[/dim]"))

    if cfg.ingest.get("warn_homepage_urls", True):
        from urllib.parse import urlparse
        bare = [r for r in rows
                if not (urlparse(r["source_url"]).path or "/").strip("/")
                and not urlparse(r["source_url"]).query]
        if bare:
            body = "\n".join("  · tier %s | %s" % (r["tier"], r["source_url"][:66])
                             for r in bare[:8])
            if len(bare) > 8:
                body += "\n  · ... con %d dong nua" % (len(bare) - 8)
            body += ("\n\n[dim]Trang chu hiem khi la cho dat backlink. Neu day la cot"
                     " 'Ten Mien' thi khai bao 'ingest.sheet_columns' de lay dung cot"
                     " link.[/dim]")
            console.print(tui.warn_panel("%d URL chi co ten mien" % len(bare), body))

    if dry_run:
        console.print("\n[yellow]Che do thu — khong ghi file.[/yellow]\n")
        return rows

    out = ingest_mod.write_master(rows, cfg.master_csv)
    console.print(tui.ok_panel("Nap du lieu xong",
                              "%d link sach  →  %s" % (len(rows), out)))
    console.print()
    return rows


# ------------------------------------------------------------------ buoc check
def _do_check_tier(cfg, all_rows, targets, tier, limit, force_js, no_js):
    rows = [r for r in all_rows if str(r["tier"]) == str(tier)]
    if limit:
        rows = rows[:limit]
    if not rows:
        console.print("  [dim]tier %s: khong co link nao, bo qua[/dim]" % tier)
        return []

    use_js = cfg.js_for_tier(tier, force_js)
    if no_js:
        use_js = False

    label = cfg.tiers[int(tier)].label if int(tier) in cfg.tiers else "tier %s" % tier
    counts = defaultdict(int)

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[stat]}"),
        TimeElapsedColumn(),
        console=console,
    )
    with progress:
        task = progress.add_task(
            "[cyan]Tier %s[/cyan] %s" % (tier, "[dim]· JS[/dim]" if use_js else ""),
            total=len(rows), stat="")

        def fmt():
            return ("[green]%d song[/green] [yellow]%d mat[/yellow] [red]%d loi[/red]"
                    % (counts["FOUND"], counts["NOT_FOUND"], counts["PAGE_ERROR"]))

        def on_progress(res):
            counts[res.status] += 1
            progress.advance(task)
            progress.update(task, stat=fmt())

        js_task = {"t": None}

        def on_js_start(n):
            js_task["t"] = progress.add_task(
                "[magenta]  render JS[/magenta]", total=n, stat="")

        def on_js_progress(res):
            if js_task["t"] is not None:
                progress.advance(js_task["t"])

        results = asyncio.run(checker.run_check(
            cfg, rows, targets, use_js, on_progress=on_progress,
            on_js_start=on_js_start, on_js_progress=on_js_progress, quiet=True))

    return results


def _write_outputs(cfg, results, tier_label, today, out_override=None):
    paths = []
    if out_override:
        base = Path(out_override)
        csv_p, xlsx_p = base.with_suffix(".csv"), base.with_suffix(".xlsx")
    else:
        csv_p = cfg.out_path(today, tier_label, "csv")
        xlsx_p = cfg.out_path(today, tier_label, "xlsx")
    formats = [f.lower() for f in cfg.output["formats"]]
    if "csv" in formats:
        checker.write_csv(results, csv_p)
        paths.append(csv_p)
    if "xlsx" in formats:
        report_mod.write_xlsx(results, xlsx_p, cfg)
        paths.append(xlsx_p)
    return paths


def _find_previous(cfg, tier_label, today):
    """Tim file ket qua gan nhat cua cung tier, truoc ngay hom nay."""
    d = Path(cfg.output["dir"])
    if not d.exists():
        return None
    pat = "*_%s_tier%s.csv" % (cfg.site_name, tier_label)
    cands = sorted(p for p in d.glob(pat) if not p.name.startswith(today))
    return cands[-1] if cands else None


# --------------------------------------------------------------------- lenh
@app.command()
def run(
    config_path: str = typer.Option(DEFAULT_CONFIG, "--config", "-c", help="File cau hinh YAML"),
    tier: str = typer.Option(None, "--tier", "-t", help="Chi chay mot tier, vd -t 1"),
    limit: int = typer.Option(None, "--limit", "-n", help="Chi check N link dau moi tier (thu nhanh)"),
    skip_ingest: bool = typer.Option(False, "--skip-ingest", help="Dung master CSV co san, khong tai lai Google Sheet"),
    js: bool = typer.Option(False, "--js", help="Ep bat render JS cho moi tier"),
    no_js: bool = typer.Option(False, "--no-js", help="Tat render JS du config bat"),
    no_diff: bool = typer.Option(False, "--no-diff", help="Bo qua buoc so sanh voi lan chay truoc"),
):
    """Chay tron goi: nap du lieu → check tung tier → xuat bao cao."""
    tui.show_banner()
    cfg = _load(config_path)

    tiers_to_run = ([int(tier)] if tier
                    else sorted(cfg.tiers, key=lambda n: (cfg.tiers[n].priority, n)))
    for t in tiers_to_run:
        if t not in cfg.tiers:
            console.print(tui.err_panel("Tier khong ton tai",
                                        "Config chi co tier: %s" % sorted(cfg.tiers)))
            raise typer.Exit(code=1)

    console.print(tui.config_panel(cfg, _source_desc(cfg), tiers_to_run, limit))
    console.print()

    # Tier can render JS ma chua co Playwright -> ket qua tier do khong dang tin.
    js_tiers = [t for t in tiers_to_run if cfg.js_for_tier(t, js) and not no_js]
    if js_tiers and not _playwright_available():
        console.print(tui.warn_panel(
            "Chua cai Playwright",
            "Tier [bold]%s[/bold] can render JavaScript moi doc dung noi dung.\n"
            "Thieu Playwright thi cac link do se bi bao [yellow]CHUA_CAI_PLAYWRIGHT[/yellow]"
            " chu khong ket luan mat link.\n\n"
            "  [cyan]pip install playwright[/cyan]\n"
            "  [cyan]playwright install chromium[/cyan]\n\n"
            "[dim]Van chay tiep duoc — tier khong can JS cho ket qua binh thuong.[/dim]"
            % ", ".join(str(t) for t in js_tiers)))
        console.print()

    # ---------- buoc 1
    if skip_ingest or not cfg.source_url:
        if not Path(cfg.master_csv).exists():
            console.print(tui.err_panel(
                "Chua co du lieu",
                "Khong thay %s.\nDan link Google Sheet vao 'source.url' trong %s "
                "roi chay lai." % (cfg.master_csv, config_path)))
            raise typer.Exit(code=1)
        all_rows = checker.load_master(cfg.master_csv)
        console.print("[bold]› Buoc 1 — Nap du lieu[/bold]")
        console.print("  [dim]Dung file co san: %s (%d link)[/dim]\n"
                      % (cfg.master_csv, len(all_rows)))
    else:
        _do_ingest(cfg, dry_run=False)
        all_rows = checker.load_master(cfg.master_csv)

    targets = checker.build_targets(all_rows, cfg)

    # ---------- buoc 2
    console.print("[bold]› Buoc 2 — Kiem tra link[/bold]")
    console.print("  [dim]Thu tu theo priority trong config: tier %s[/dim]"
                  % " → ".join(str(t) for t in tiers_to_run))
    today = date.today().isoformat()
    results_by_tier, all_results, written = {}, [], []

    for t in tiers_to_run:
        rs = _do_check_tier(cfg, all_rows, targets, t, limit, js, no_js)
        if not rs:
            continue
        results_by_tier[str(t)] = rs
        all_results.extend(rs)
        written += _write_outputs(cfg, rs, str(t), today)

    if not all_results:
        console.print(tui.warn_panel("Khong co gi de check", "Danh sach rong."))
        raise typer.Exit(code=1)

    # ---------- buoc 3
    console.print("\n[bold]› Buoc 3 — Bao cao[/bold]")
    console.print(tui.verdict_panel(all_results))
    console.print()
    console.print(tui.tier_summary_table(results_by_tier, cfg))
    console.print()
    console.print(tui.diag_table(all_results))

    manual = tui.manual_check_list(all_results)
    if manual is not None:
        console.print()
        console.print(Panel(manual, title="[yellow]Phai mo trinh duyet kiem tra[/yellow]",
                            border_style="yellow", expand=False))

    crit = tui.critical_list(all_results)
    if crit is not None:
        console.print()
        console.print(Panel(crit, title="[red]Can xu ly ngay[/red]",
                            border_style="red", expand=False))
    else:
        console.print("\n[green]Khong co link nao o muc CHET hoac NANG.[/green]")

    # ---------- buoc 4
    if not no_diff:
        console.print("\n[bold]› Buoc 4 — So voi lan chay truoc[/bold]")
        any_prev = False
        for t in results_by_tier:
            prev = _find_previous(cfg, t, today)
            if not prev:
                continue
            any_prev = True
            cur = cfg.out_path(today, t, "csv")
            console.print("  [dim]tier %s:[/dim] %s → %s" % (t, prev.name, cur.name))
            import compare as compare_mod
            old, new = compare_mod.load(str(prev)), compare_mod.load(str(cur))
            lost = [u for u, n in new.items()
                    if old.get(u) and old[u]["status"] == "FOUND" and n["status"] != "FOUND"]
            back = [u for u, n in new.items()
                    if old.get(u) and old[u]["status"] != "FOUND" and n["status"] == "FOUND"]
            console.print("    [red]vua mat: %d[/red]   [green]vua khoi phuc: %d[/green]"
                          % (len(lost), len(back)))
            for u in lost[:8]:
                console.print("      [red]-[/red] %s" % u[:76])
        if not any_prev:
            console.print("  [dim]Chua co lan chay truoc de so sanh. "
                          "Lan sau chay lai se co.[/dim]")

    body = Table.grid(padding=(0, 2))
    body.add_column(style="dim")
    body.add_column()
    body.add_row("Da check", "%d link" % len(all_results))
    body.add_row("File ket qua", "\n".join(str(p) for p in written))
    body.add_row("Mo file", "[cyan]%s[/cyan]" % (written[-1] if written else ""))
    console.print()
    console.print(tui.ok_panel("Hoan tat", body))
    console.print()


@app.command()
def ingest(
    config_path: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    url: str = typer.Option("", "--url", help="Ghi de source.url trong config"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Chi xem truoc, khong ghi file"),
):
    """Chi nap + lam sach du lieu tu Google Sheet/Docs."""
    tui.show_banner()
    cfg = _load(config_path)
    _do_ingest(cfg, dry_run=dry_run, url=url)


@app.command()
def check(
    config_path: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    tier: str = typer.Option(None, "--tier", "-t"),
    limit: int = typer.Option(None, "--limit", "-n"),
    js: bool = typer.Option(False, "--js"),
    no_js: bool = typer.Option(False, "--no-js"),
):
    """Chi check, khong nap lai du lieu (tuong duong run --skip-ingest)."""
    run(config_path=config_path, tier=tier, limit=limit, skip_ingest=True,
        js=js, no_js=no_js, no_diff=False)


@app.command()
def diff(
    old_csv: str = typer.Argument(..., help="Ket qua lan truoc"),
    new_csv: str = typer.Argument(..., help="Ket qua lan moi"),
    output: str = typer.Option(None, "--output", "-o", help="Luu thay doi ra CSV"),
):
    """So sanh hai lan chay."""
    import compare as compare_mod
    argv = [old_csv, new_csv] + (["-o", output] if output else [])
    sys.argv = ["compare.py"] + argv
    compare_mod.main()


@app.command()
def doisoat(
    config_path: str = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    url: str = typer.Option("", "--url", help="Ghi de source.url trong config"),
    output: str = typer.Option("", "--output", "-o", help="Duong dan file xlsx"),
    results_dir: str = typer.Option("", "--results-dir",
                                    help="Thu muc chua ket qua check"),
):
    """Doi soat voi ben cung cap: ho dua bao nhieu, ta nhan bao nhieu, doi bu bao nhieu."""
    import doisoat as ds_mod

    cfg = _load(config_path)
    thu_muc = results_dir or None

    console.print("[bold]› Doi soat nguon backlink[/bold]")
    with console.status("[cyan]Dang tai lai nguon goc de dem...[/cyan]", spinner="dots"):
        try:
            bang, rows, unmatched, file_kq, trung = ds_mod.build(cfg, url, thu_muc)
        except SystemExit as e:
            console.print(tui.err_panel("Khong tai duoc nguon du lieu", e))
            raise typer.Exit(code=1)

    console.print()
    console.print(tui.doisoat_table(bang))
    console.print()
    console.print(tui.doisoat_panel(bang, trung))

    if trung:
        console.print()
        console.print(tui.trung_cap_table(trung))
        console.print()
        console.print(tui.trung_table(trung))

    if not file_kq:
        console.print(tui.warn_panel(
            "Chua co ket qua check nao",
            "Cot 'Chet' dang bang 0 vi chua chay check, khong phai vi khong co "
            "link chet.\n\n[dim]Chay 'blcheck run' truoc roi doi soat lai.[/dim]"))
    if unmatched:
        console.print(tui.warn_panel(
            "%d tab khong khop tier nao" % len(unmatched),
            "\n".join("  · %s" % t for t in unmatched)
            + "\n\n[dim]Nhung tab nay khong duoc dem. Them tu khoa vao "
              "'tiers.<N>.match' trong config neu day la link that.[/dim]"))

    kq, _ = ds_mod.doc_ket_qua(cfg, thu_muc)
    out = output or str(Path(cfg.output.get("dir", "results"))
                        / ("%s_%s_doi-soat.xlsx"
                           % (date.today().isoformat(), cfg.site_name)))
    p = ds_mod.write_xlsx(bang, out, cfg, rows, file_kq, kq, trung)
    console.print()
    console.print(tui.ok_panel("Doi soat xong",
                               "File gui cho ben cung cap  →  %s" % p))
    console.print()


@app.command()
def version():
    """Hien phien ban."""
    console.print("%s v%s" % (__app_name__, __version__))


if __name__ == "__main__":
    app()
