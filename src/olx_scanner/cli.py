from __future__ import annotations

import argparse
import hashlib
import os
import re
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from rich.box import ROUNDED
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from olx_scanner.ai.client import DeepSeekAnalyzer
from olx_scanner.ai.heuristics import is_likely_iphone_offer
from olx_scanner.core.config import init_environment
from olx_scanner.i18n.translations import get_language, set_language, t
from olx_scanner.scraper.client import TLSScraper
from olx_scanner.scraper.proxy import select_best_olx_proxies
from olx_scanner.storage.database import Database
from olx_scanner.ui.dashboard import render_dashboard
from olx_scanner.ui.state import DashboardState
from olx_scanner.ui.wizard import get_or_init_config

STOP_EVENT = threading.Event()
LOG_LOCK = threading.Lock()
LOG_FILE_PATH: Path = Path("olx_scanner.log")
ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*m")
GLOBAL_STATE = DashboardState()


def log_to_file(msg: str, level: str = "INFO", idx: str | int | None = None) -> None:
    level_upper = level.upper()
    now = time.time()
    time_s = time.strftime("%H:%M:%S", time.localtime(now)) + f".{int((now % 1) * 1000):03d}"
    date_s = time.strftime("%Y-%m-%d", time.localtime(now))
    prefix = f"[{idx}]" if idx is not None else "[*]"
    clean_msg = ANSI_REGEX.sub("", msg)
    line = f"{date_s} {time_s} {prefix:<12} [{level_upper:<7}] {clean_msg}\n"

    with LOG_LOCK:
        try:
            with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


def app_logger(msg: str, level: str = "INFO", idx: str | int | None = None) -> None:
    log_to_file(msg, level, idx)
    if level.upper() in ("SUCCESS", "WARN", "ERROR", "AI", "PROXY", "SMART"):
        clean_preview = ANSI_REGEX.sub("", msg)
        if len(clean_preview) > 95:
            clean_preview = clean_preview[:92] + "..."
        GLOBAL_STATE.add_event(level.upper(), clean_preview, str(idx) if idx else None)


def sync_db_stats_to_dashboard(db: Database) -> None:
    stats = db.get_stats()
    recent = db.get_recent_analyzed(limit=12)
    with GLOBAL_STATE.lock:
        GLOBAL_STATE.total_offers_db = stats["total"]
        GLOBAL_STATE.analyzed_offers_db = stats["analyzed"]
        GLOBAL_STATE.damaged_offers_db = stats["damaged"]
        GLOBAL_STATE.healthy_offers_db = max(0, stats["analyzed"] - stats["damaged"])
        GLOBAL_STATE.table_rows = [dict(row) for row in recent]


def process_single_offer(
    offer: dict,
    proxy_used: str | None,
    scraper: TLSScraper,
    ai: DeepSeekAnalyzer,
    db: Database,
) -> None:
    olx_id = str(offer.get("olx_id", "UNKNOWN"))
    if STOP_EVENT.is_set() or db.is_already_analyzed(olx_id):
        return

    try:
        details = scraper.fetch_full_offer_details(offer["url"], proxy_used, idx=olx_id)
        if STOP_EVENT.is_set():
            return

        if details.get("price") is not None:
            offer["price"] = details["price"]
        if details.get("description"):
            offer["description"] = details["description"]
        if details.get("posted_at"):
            offer["posted_at"] = details["posted_at"]
        if details.get("location"):
            offer["location"] = details["location"]

        params_text = details.get("params_text", "")
        if not offer["description"] and not params_text:
            return

        db.insert_raw_offer(offer)

        is_phone, reason = is_likely_iphone_offer(
            title=offer["title"],
            description=offer["description"],
            price=offer.get("price"),
        )
        if not is_phone:
            db.update_ai_analysis(olx_id, {
                "exact_model": None,
                "storage_gb": None,
                "color": None,
                "battery_health_pct": None,
                "condition": t("badge_accessory"),
                "is_damaged": False,
                "damage_details": reason,
                "face_id_working": None,
                "icloud_clean": None,
                "ai_verdict": f"Pominięto: {reason}",
            })
            return

        ai_data, _ = ai.analyze_listing(
            title=offer["title"],
            price=offer["price"],
            params_text=params_text,
            description=offer["description"],
            idx=olx_id,
        )

        if STOP_EVENT.is_set():
            return

        if ai_data:
            db.update_ai_analysis(olx_id, ai_data)
            model = ai_data.get("exact_model") or offer["title"][:20]
            bat = f"{ai_data.get('battery_health_pct')}%" if ai_data.get("battery_health_pct") else "?"
            dam = t("badge_damaged") if ai_data.get("is_damaged") else t("badge_ok")
            app_logger(t("offer_recognized", model=model, battery=bat, status=dam), "SUCCESS", idx=olx_id)

    except Exception as e:
        log_to_file(f"Error processing {olx_id}: {e}", "ERROR", idx=olx_id)


def run_single_scan_cycle(args: argparse.Namespace, db: Database, scraper: TLSScraper, ai: DeepSeekAnalyzer) -> None:
    with GLOBAL_STATE.lock:
        GLOBAL_STATE.early_stopping_active = False

    GLOBAL_STATE.set_status(t("status_pages_checking"))
    GLOBAL_STATE.set_progress(0.05, t("status_pages_checking"))

    all_new_queue: list[tuple[dict, str | None]] = []
    seen_ids: set[str] = set()

    pending_in_db = db.get_pending_unanalyzed_offers(limit=30)
    if pending_in_db:
        app_logger(t("resuming_pending", count=len(pending_in_db)), "SMART")
        for p_off in pending_in_db:
            seen_ids.add(str(p_off["olx_id"]))
            all_new_queue.append((p_off, None))

    for page in range(1, args.pages + 1):
        if STOP_EVENT.is_set():
            return

        GLOBAL_STATE.set_status(t("status_scanning_page", page=page, total=args.pages))
        GLOBAL_STATE.set_progress(0.08 + (0.15 * (page / args.pages)), t("status_scanning_page", page=page, total=args.pages))

        t_start = time.perf_counter()
        status, offers, used_proxy = scraper.fetch_page(page=page)
        duration = time.perf_counter() - t_start

        if status != 200 or not offers:
            app_logger(f"Page {page}: HTTP {status} / empty response", "WARN")
            continue

        page_ids = [str(o["olx_id"]) for o in offers]
        fingerprint = hashlib.md5(",".join(page_ids).encode()).hexdigest()[:12]
        last_fingerprint = db.get_last_page_fingerprint(page)

        new_on_page = 0
        for off in offers:
            oid = str(off["olx_id"])
            if oid in seen_ids or db.offer_exists(oid):
                with GLOBAL_STATE.lock:
                    GLOBAL_STATE.smart_skipped_duplicates += 1
            else:
                seen_ids.add(oid)
                all_new_queue.append((off, used_proxy))
                new_on_page += 1

        db.record_page_scan(
            page_number=page,
            offers_total=len(offers),
            new_offers=new_on_page,
            fingerprint=fingerprint,
            duration_s=duration,
        )

        if page > 1 and new_on_page == 0:
            with GLOBAL_STATE.lock:
                GLOBAL_STATE.early_stopping_active = True
            app_logger(t("early_stop_hit", page=page, total=args.pages), "SMART")
            break
        elif page == 1 and last_fingerprint == fingerprint and new_on_page == 0:
            with GLOBAL_STATE.lock:
                GLOBAL_STATE.early_stopping_active = True
            app_logger(t("page_identical"), "SMART")
            break

    sync_db_stats_to_dashboard(db)

    total_to_process = len(all_new_queue)
    if total_to_process == 0 or STOP_EVENT.is_set():
        GLOBAL_STATE.set_status(t("status_all_up_to_date"))
        GLOBAL_STATE.set_progress(1.0, t("status_cycle_complete"))
        return

    GLOBAL_STATE.set_status(t("status_ai_processing", count=total_to_process))
    app_logger(f"Queue AI: {total_to_process} offers", "AI")

    completed = 0
    executor = ThreadPoolExecutor(max_workers=args.threads)
    futures = [executor.submit(process_single_offer, offer, proxy_used, scraper, ai, db) for offer, proxy_used in all_new_queue]

    try:
        for _future in as_completed(futures):
            if STOP_EVENT.is_set():
                break
            completed += 1
            ratio = 0.25 + (0.75 * (completed / total_to_process))
            GLOBAL_STATE.set_progress(ratio, f"AI: {completed}/{total_to_process}")
            GLOBAL_STATE.set_status(f"AI: {completed}/{total_to_process}")
            sync_db_stats_to_dashboard(db)
    except KeyboardInterrupt:
        STOP_EVENT.set()
        executor.shutdown(wait=False, cancel_futures=True)
        raise

    executor.shutdown(wait=True)
    sync_db_stats_to_dashboard(db)
    GLOBAL_STATE.set_status(t("status_cycle_complete"))
    GLOBAL_STATE.set_progress(1.0, f"OK ({completed})")


def print_final_summary(console: Console, db: Database) -> None:
    stats = db.get_stats()
    recent = db.get_recent_analyzed(limit=15)

    console.print("\n")
    table = Table(
        title=t("final_table_title"),
        box=ROUNDED,
        border_style="cyan",
        header_style="bold bright_cyan",
        expand=True,
    )
    table.add_column(t("col_model"), ratio=22, style="bold white")
    table.add_column(t("col_price"), justify="right", ratio=12, style="bold yellow")
    table.add_column(t("col_battery"), justify="center", ratio=10)
    table.add_column(t("col_condition"), ratio=26)
    table.add_column(t("col_verdict"), ratio=30)

    for r in recent:
        storage_s = f" {r['storage_gb']}GB" if r['storage_gb'] else ""
        model_s = f"{r['model_name'] or r['title'][:22]}{storage_s}"
        price_s = f"{r['price']:.0f} zł" if r['price'] is not None else "[dim]Brak[/dim]"

        bat_val = r['battery_health_pct']
        if bat_val:
            bat_color = "bright_green" if bat_val >= 85 else ("bright_yellow" if bat_val >= 78 else "bright_red")
            bat_s = f"[{bat_color}]{bat_val}%[/{bat_color}]"
        else:
            bat_s = "[dim]?[/dim]"

        dam_badge = f"[bold red]{t('badge_damaged')}[/bold red] " if r['is_damaged'] else f"[bold green]{t('badge_ok')}[/bold green] "
        stan_s = f"{dam_badge}{r['condition_state'] or ''}"

        table.add_row(model_s, price_s, bat_s, stan_s, r['ai_summary'] or "-")

    console.print(table)
    console.print(
        Panel.fit(
            f"{t('kpi_total')}: [bold white]{stats['total']}[/bold white] │ "
            f"{t('kpi_analyzed')}: [bold cyan]{stats['analyzed']}[/bold cyan] │ "
            f"{t('kpi_healthy')}: [bold green]{max(0, stats['analyzed'] - stats['damaged'])}[/bold green] │ "
            f"{t('kpi_damaged')}: [bold red]{stats['damaged']}[/bold red]\n"
            f"[dim]Log file: {LOG_FILE_PATH}[/dim]",
            title=t("report_title"),
            border_style="green",
        )
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OLX iPhone Scanner with DeepSeek AI and Multi-language support.")
    p.add_argument("--setup", "--reconfigure", action="store_true", help="Launch the interactive setup wizard")
    p.add_argument("--lang", choices=["en", "pl", "uk", "de", "be"], default=None, help="Force UI & prompt language")
    p.add_argument("--api-key", default=None, help="DeepSeek API Key override")
    p.add_argument("--model", default=None, help="DeepSeek model name")
    p.add_argument("--proxy", default=None, help="Static proxy URL override")
    p.add_argument("--proxy-file", "-pf", default=None, help="Custom proxy file override")
    p.add_argument("--min-proxies", type=int, default=15, help="Minimum proxies required in pool")
    p.add_argument("--proxy-workers", type=int, default=150, help="Proxy checker threads")
    p.add_argument("--pages", type=int, default=None, help="Pages to scan per cycle")
    p.add_argument("--threads", type=int, default=None, help="AI analysis threads")
    p.add_argument("--watch", action="store_true", help="Enable continuous monitoring loop")
    p.add_argument("--interval", type=int, default=None, help="Watch mode interval in seconds")
    p.add_argument("--inline", action="store_true", help="Run in inline scrolling mode (no full-screen TUI)")
    p.add_argument("--log-file", default="olx_scanner.log", help="Log file path")
    return p.parse_args()


def main() -> int:
    global LOG_FILE_PATH
    init_environment()
    args = parse_args()
    console = Console()

    cfg = get_or_init_config(force_setup=args.setup, console=console)

    chosen_lang = args.lang or cfg.get("language", "en")
    set_language(chosen_lang)

    api_key = args.api_key or cfg.get("api_key") or os.getenv("DEEPSEEK_API_KEY", "")
    model_name = args.model or cfg.get("model") or "deepseek-v4-flash-vision-exp"
    proxy_val = args.proxy if args.proxy is not None else cfg.get("custom_proxy")
    proxy_file_val = args.proxy_file if args.proxy_file is not None else cfg.get("proxy_file")
    pages_count = args.pages if args.pages is not None else cfg.get("pages", 3)
    threads_count = args.threads if args.threads is not None else cfg.get("threads", 8)
    watch_mode = args.watch or cfg.get("watch", False)
    interval_seconds = args.interval if args.interval is not None else cfg.get("interval", 120)

    args.pages = pages_count
    args.threads = threads_count
    args.watch = watch_mode
    args.interval = interval_seconds
    args.model = model_name
    args.proxy = proxy_val
    args.proxy_file = proxy_file_val

    LOG_FILE_PATH = Path(args.log_file)
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*75}\n=== START OLX SCANNER [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Lang: {get_language()} ===\n{'='*75}\n")
    except Exception:
        pass

    def sigint_handler(sig, frame):
        GLOBAL_STATE.set_status("[bold red]Ctrl+C detected. Stopping...[/bold red]")
        STOP_EVENT.set()

    signal.signal(signal.SIGINT, sigint_handler)

    verified_proxies = []
    if not args.proxy:
        verified_proxies = select_best_olx_proxies(
            custom_file=args.proxy_file,
            min_working=args.min_proxies,
            max_workers=args.proxy_workers,
            console=console,
            logger=app_logger,
        )

    scraper = TLSScraper(verified_proxies=verified_proxies, static_proxy=args.proxy, logger=app_logger)
    ai = DeepSeekAnalyzer(api_key=api_key, model=args.model, language=chosen_lang, logger=app_logger)
    db = Database("olx_iphones.db", logger=app_logger)

    GLOBAL_STATE.model_name = args.model
    GLOBAL_STATE.proxy_count = len(verified_proxies) if verified_proxies else (1 if args.proxy else 0)
    GLOBAL_STATE.current_status = t("status_init")
    GLOBAL_STATE.progress_label = t("waiting_label")
    sync_db_stats_to_dashboard(db)

    def live_render_generator():
        return render_dashboard(GLOBAL_STATE, console.size)

    with Live(
        get_renderable=live_render_generator,
        console=console,
        screen=not args.inline,
        refresh_per_second=8,
        auto_refresh=True,
        vertical_overflow="ellipsis",
    ):
        try:
            while not STOP_EVENT.is_set():
                run_single_scan_cycle(args, db, scraper, ai)

                if not args.watch or STOP_EVENT.is_set():
                    break

                GLOBAL_STATE.set_status(t("waiting_label"))
                for remaining in range(args.interval, 0, -1):
                    if STOP_EVENT.is_set():
                        break
                    with GLOBAL_STATE.lock:
                        GLOBAL_STATE.next_scan_seconds = remaining
                    time.sleep(1)

                with GLOBAL_STATE.lock:
                    GLOBAL_STATE.next_scan_seconds = 0
                    GLOBAL_STATE.cycle_index += 1

        except KeyboardInterrupt:
            STOP_EVENT.set()

    print_final_summary(console, db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
