#!/usr/bin/env python3
import sys
import os
import yaml
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crunchyroll.auth import CRAuth, CRAuthError, DEFAULT_CLIENT_ID, DEFAULT_CLIENT_SECRET
from src.crunchyroll.history import CRHistory
from src.storage.history_store import HistoryStore
from src.exporters.anilist import AniListExporter
from src.exporters.mal import MALExporter, get_auth_url as mal_auth_url, exchange_code as mal_exchange
from src.exporters.mal_xml import MALXMLExporter

console = Console()


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--config", "-c", default="config.yaml", show_default=True, help="Path to config file.")
@click.pass_context
def cli(ctx, config):
    ctx.ensure_object(dict)
    if Path(config).exists():
        ctx.obj["config"] = load_config(config)
    else:
        ctx.obj["config"] = {}
    ctx.obj["config_path"] = config


@cli.command()
@click.option("--etp-rt", default=None, help="Value of the etp_rt cookie from your browser session. Can also be set in config.yaml under crunchyroll.etp_rt.")
@click.option("--replace", is_flag=True, default=False, help="Replace ALL existing local history instead of merging (incremental by default).")
@click.pass_context
def fetch(ctx, etp_rt, replace):
    """Fetch your Crunchyroll watch history and save it locally as JSON.

    \b
    HOW TO GET THE etp_rt COOKIE:
      1. Log into crunchyroll.com in your browser
      2. Open DevTools (F12) -> Application tab -> Cookies -> https://www.crunchyroll.com
      3. Copy the value of the 'etp_rt' cookie

    \b
    EXAMPLES:
      python src/main.py fetch --etp-rt "your-cookie-value"
      python src/main.py fetch                   (reads etp_rt from config.yaml)
      python src/main.py fetch --replace         (full resync, discards local cache)
    """
    cfg = ctx.obj["config"]
    store_path = cfg.get("storage", {}).get("path", "data/history.json")

    cr_cfg = cfg.get("crunchyroll", {})
    etp_rt = etp_rt or cr_cfg.get("etp_rt") or ""
    if not etp_rt:
        etp_rt = click.prompt("etp_rt cookie value", hide_input=True)

    auth = CRAuth(
        client_id=cr_cfg.get("client_id") or DEFAULT_CLIENT_ID,
        client_secret=cr_cfg.get("client_secret") or DEFAULT_CLIENT_SECRET,
    )

    with console.status("[bold green]Logging in to Crunchyroll..."):
        try:
            token = auth.login_with_etp_rt(etp_rt)
        except CRAuthError as e:
            console.print(f"[red]Authentication failed:[/red] {e}")
            raise SystemExit(1)

    console.print(f"[green]Logged in.[/green] Account ID: {token.account_id}")

    with console.status("[bold green]Fetching watch history..."):
        history = CRHistory(token)
        episodes = history.fetch_all(locale=cfg.get("locale", "en-US"))

    store = HistoryStore(Path(store_path))
    if replace:
        store.replace(episodes)
        console.print(f"[green]Saved {len(episodes)} episodes[/green] to {store_path} (replaced).")
    else:
        added = store.update(episodes)
        console.print(
            f"[green]Sync complete.[/green] {added} new episodes added. "
            f"Total: {len(store)} episodes across {len(store.series_summaries())} series."
        )


@cli.command()
@click.pass_context
def status(ctx):
    """Show a summary of locally stored watch history.

    \b
    Displays a table with each series, number of episodes watched,
    and the highest episode number seen. Run 'fetch' first.
    """
    cfg = ctx.obj["config"]
    store_path = cfg.get("storage", {}).get("path", "data/history.json")
    store = HistoryStore(Path(store_path))

    if len(store) == 0:
        console.print("[yellow]No history found. Run [bold]fetch[/bold] first.[/yellow]")
        return

    table = Table(title="Watch History Summary", show_lines=True)
    table.add_column("Series", style="cyan", no_wrap=False)
    table.add_column("Episodes watched", justify="right")
    table.add_column("Max episode", justify="right")

    for s in sorted(store.series_summaries(), key=lambda x: x.series_title):
        table.add_row(s.series_title, str(s.total_watched), str(s.max_episode))

    console.print(table)
    console.print(f"\nLast sync: {store.last_sync or 'never'}")


@cli.command()
@click.option("--target", "-t",
              type=click.Choice(["anilist", "mal", "xml", "all"]),
              default="all", show_default=True,
              help="Where to export: anilist, mal, xml (local file), or all three at once.")
@click.pass_context
def export(ctx, target):
    """Export watch history to AniList, MyAnimeList and/or a local XML file.

    \b
    TARGETS:
      anilist   Updates your AniList anime list via API (requires token in config.yaml)
      mal       Updates your MyAnimeList via API (requires OAuth setup in config.yaml)
      xml       Generates data/animelist.xml, importable at myanimelist.net/import.php
      all       Runs all three targets (default)

    \b
    FIRST-TIME SETUP:
      AniList:  Create app at anilist.co/settings/developer, then run with --target anilist
                and follow the printed instructions to get your access token.
      MAL:      Create app at myanimelist.net/apiconfig, add client_id to config.yaml,
                then run with --target mal and follow the OAuth flow.
      XML:      No setup needed, works out of the box.

    \b
    EXAMPLES:
      python src/main.py export                    (export to all targets)
      python src/main.py export --target xml       (local XML only, no auth needed)
      python src/main.py export --target anilist   (AniList only)
    """
    cfg = ctx.obj["config"]
    store_path = cfg.get("storage", {}).get("path", "data/history.json")
    store = HistoryStore(Path(store_path))

    if len(store) == 0:
        console.print("[yellow]No history to export. Run [bold]fetch[/bold] first.[/yellow]")
        return

    summaries = store.series_summaries()
    console.print(f"Exporting {len(summaries)} series...")

    if target in ("xml", "all"):
        _export_xml(cfg, summaries)

    if target in ("anilist", "all"):
        _export_anilist(cfg, summaries)

    if target in ("mal", "all"):
        _export_mal(cfg, summaries)


def _export_xml(cfg: dict, summaries):
    xml_path = cfg.get("exporters", {}).get("mal_xml", {}).get("path", "data/animelist.xml")
    with console.status("[bold]Generating MAL XML..."):
        result = MALXMLExporter(xml_path).export(summaries)
    console.print(f"[green]XML exported:[/green] {xml_path} ({len(result.updated)} series)")


def _export_anilist(cfg: dict, summaries):
    al_cfg = cfg.get("exporters", {}).get("anilist", {})
    token = al_cfg.get("access_token")
    if not token:
        client_id = al_cfg.get("client_id", "")
        url = AniListExporter.get_auth_url(client_id)
        console.print(f"\n[yellow]AniList:[/yellow] No access token found.")
        console.print(f"1. Open this URL to get your token:\n   [link]{url}[/link]")
        console.print("2. After authorizing, copy the [bold]access_token[/bold] from the redirect URL.")
        console.print("3. Add it to config.yaml under [bold]exporters.anilist.access_token[/bold].")
        return

    with console.status("[bold]Exporting to AniList..."):
        result = AniListExporter(token).export(summaries)
    _print_result("AniList", result)


def _export_mal(cfg: dict, summaries):
    mal_cfg = cfg.get("exporters", {}).get("mal", {})
    token = mal_cfg.get("access_token")
    if not token:
        client_id = mal_cfg.get("client_id", "")
        client_secret = mal_cfg.get("client_secret", "")
        if not client_id:
            console.print("[yellow]MAL:[/yellow] Set [bold]exporters.mal.client_id[/bold] in config.yaml first.")
            return
        url, verifier = mal_auth_url(client_id)
        console.print(f"\n[yellow]MAL OAuth:[/yellow] Open this URL to authorize:\n  {url}")
        console.print("After authorizing, MAL redirects to http://localhost/?code=XXXX")
        console.print("The page won't load — that's normal. Copy the [bold]code=[/bold] value from the URL bar.")
        code = click.prompt("Paste the authorization code")
        with console.status("Exchanging code for token..."):
            token = mal_exchange(client_id, code, verifier, client_secret)
        console.print(f"[green]Token obtained.[/green] Save it in config.yaml under exporters.mal.access_token")

    with console.status("[bold]Exporting to MyAnimeList..."):
        result = MALExporter(token).export(summaries)
    _print_result("MyAnimeList", result)


def _print_result(name: str, result):
    console.print(f"\n[bold]{name}[/bold] — {len(result.updated)} updated, "
                  f"{len(result.skipped)} skipped, {len(result.failed)} failed")
    for title, reason in result.failed:
        console.print(f"  [red]FAIL[/red] {title}: {reason}")


@cli.command()
@click.option("--target", "-t",
              type=click.Choice(["anilist", "mal", "xml", "all"]),
              default="all", show_default=True,
              help="Export targets to include in the sync.")
@click.pass_context
def sync(ctx, target):
    """Fetch new history from Crunchyroll then export in one step.

    \b
    Requires etp_rt set in config.yaml (unattended use, no prompts).
    Intended for scheduled/automated runs.

    \b
    EXAMPLES:
      python src/main.py sync
      python src/main.py sync --target anilist
    """
    cfg = ctx.obj["config"]
    cr_cfg = cfg.get("crunchyroll", {})
    etp_rt = cr_cfg.get("etp_rt", "")
    if not etp_rt:
        console.print("[red]sync requires etp_rt set in config.yaml[/red]")
        raise SystemExit(1)

    ctx.invoke(fetch, etp_rt=etp_rt, replace=False)
    ctx.invoke(export, target=target)


@cli.command()
@click.option("--time", "run_at", default="08:00", show_default=True,
              help="Time to run daily in HH:MM format.")
@click.option("--target", "-t",
              type=click.Choice(["anilist", "mal", "xml", "all"]),
              default="all", show_default=True,
              help="Export targets.")
@click.option("--remove", is_flag=True, default=False,
              help="Remove the scheduled task instead of creating it.")
@click.pass_context
def schedule(ctx, run_at, target, remove):
    """Register a daily auto-sync task in Windows Task Scheduler or cron.

    \b
    Requires etp_rt set in config.yaml before scheduling.

    \b
    EXAMPLES:
      python src/main.py schedule                      (daily at 08:00)
      python src/main.py schedule --time 20:00         (daily at 20:00)
      python src/main.py schedule --remove             (delete the task)
    """
    import sys
    import platform
    import subprocess
    from pathlib import Path

    task_name = "CrunchyExporter"
    project_dir = Path(__file__).parent.parent.resolve()
    python = sys.executable
    config_path = ctx.obj.get("config_path", "config.yaml")
    cmd = f'"{python}" "{project_dir / "src" / "main.py"}" -c "{config_path}" sync --target {target}'

    if platform.system() == "Windows":
        _schedule_windows(task_name, cmd, run_at, remove)
    else:
        _schedule_cron(cmd, run_at, remove)


def _schedule_windows(task_name: str, cmd: str, run_at: str, remove: bool):
    import subprocess
    if remove:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            console.print(f"[green]Task '{task_name}' removed.[/green]")
        else:
            console.print(f"[red]Could not remove task:[/red] {result.stderr.strip()}")
        return

    result = subprocess.run(
        ["schtasks", "/Create",
         "/TN", task_name,
         "/TR", cmd,
         "/SC", "DAILY",
         "/ST", run_at,
         "/F"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        console.print(f"[green]Scheduled:[/green] '{task_name}' runs daily at {run_at}.")
        console.print(f"  Command: {cmd}")
    else:
        console.print(f"[red]Failed to create task:[/red] {result.stderr.strip()}")


def _schedule_cron(cmd: str, run_at: str, remove: bool):
    import subprocess
    hour, minute = run_at.split(":")
    cron_entry = f"{minute} {hour} * * * {cmd}  # CrunchyExporter"

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""
    lines = [l for l in existing.splitlines() if "CrunchyExporter" not in l]

    if remove:
        new_crontab = "\n".join(lines) + "\n"
        subprocess.run(["crontab", "-"], input=new_crontab, text=True)
        console.print("[green]CrunchyExporter cron entry removed.[/green]")
        return

    lines.append(cron_entry)
    new_crontab = "\n".join(lines) + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    console.print(f"[green]Cron job added:[/green] runs daily at {run_at}.")
    console.print(f"  {cron_entry}")


if __name__ == "__main__":
    cli()
