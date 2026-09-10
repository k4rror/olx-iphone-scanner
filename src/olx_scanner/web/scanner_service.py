from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from olx_scanner.ai.client import DeepSeekAnalyzer
from olx_scanner.ai.heuristics import is_likely_iphone_offer
from olx_scanner.core.config import load_config
from olx_scanner.core.regions import get_region_display_name, normalize_region
from olx_scanner.scraper.client import TLSScraper
from olx_scanner.storage.database import Database

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
RICH_TAG_RE = re.compile(r"\[/?[a-zA-Z0-9_\s#=\-:\.]+\]")


def clean_dashboard_text(text: str) -> str:
    """Usuwa kody ANSI i znaczniki formatowania Rich, przygotowując czysty tekst dla UI."""
    clean = ANSI_ESCAPE_RE.sub("", text)
    clean = RICH_TAG_RE.sub("", clean)
    return clean.strip()


class ScannerService:
    def __init__(self, db_path: str = "olx_iphones.db") -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

        # Stan skanera
        self.is_running: bool = False
        self.status_code: str = "idle"  # idle | running | waiting | stopping | error
        self.status_message: str = "Skaner jest bezczynny"
        self.current_progress: float = 0.0
        self.progress_label: str = "Gotowy do pracy"
        self.current_cycle: int = 1
        self.next_scan_seconds: int = 0
        self.current_offer_title: str | None = None

        # Metryki sesji
        self.session_metrics = {
            "total_found": 0,
            "ai_analyzed": 0,
            "healthy": 0,
            "damaged": 0,
            "duplicates_skipped": 0,
            "accessories_filtered": 0,
        }

        # Bufor zdarzeń (ostatnie 150 logów dla UI)
        self.event_logs: deque[dict[str, Any]] = deque(maxlen=150)

    def log_event(self, level: str, message: str, idx: str | int | None = None) -> None:
        ts = time.strftime("%H:%M:%S")
        clean_msg = clean_dashboard_text(message)
        with self._lock:
            self.event_logs.append({
                "timestamp": ts,
                "level": level.upper(),
                "message": clean_msg,
                "idx": str(idx) if idx else None,
            })

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "is_running": self.is_running,
                "status_code": self.status_code,
                "status_message": self.status_message,
                "progress": round(self.current_progress, 3),
                "progress_label": self.progress_label,
                "current_cycle": self.current_cycle,
                "next_scan_seconds": self.next_scan_seconds,
                "current_offer_title": self.current_offer_title,
                "metrics": dict(self.session_metrics),
                "recent_logs": list(self.event_logs),
            }

    def start(self, config_override: dict[str, Any] | None = None) -> bool:
        with self._lock:
            if self.is_running:
                return False

            self._stop_event.clear()
            self.is_running = True
            self.status_code = "running"
            self.status_message = "Inicjalizacja skanera..."
            self.current_progress = 0.0
            self.current_cycle = 1

            self._worker_thread = threading.Thread(
                target=self._run_scanning_loop,
                args=(config_override,),
                daemon=True,
            )
            self._worker_thread.start()
            self.log_event("SUCCESS", "Uruchomiono silnik skanera z poziomu panelu sterowania.")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self.is_running:
                return False

            self.status_code = "stopping"
            self.status_message = "Zatrzymywanie procesu skanera..."
            self._stop_event.set()
            self.log_event("WARN", "Wysłano sygnał zatrzymania skanera.")
            return True

    def _process_single_offer(
        self,
        offer: dict[str, Any],
        proxy_used: str | None,
        scraper: TLSScraper,
        ai: DeepSeekAnalyzer,
        db: Database,
    ) -> None:
        olx_id = str(offer.get("olx_id", "UNKNOWN"))
        if self._stop_event.is_set() or db.is_already_analyzed(olx_id):
            return

        with self._lock:
            self.current_offer_title = offer.get("title", f"Oferta {olx_id}")

        try:
            details = scraper.fetch_full_offer_details(offer["url"], proxy_used, idx=olx_id)
            if self._stop_event.is_set():
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
                with self._lock:
                    self.session_metrics["accessories_filtered"] += 1
                db.update_ai_analysis(olx_id, {
                    "exact_model": None,
                    "storage_gb": None,
                    "color": None,
                    "battery_health_pct": None,
                    "condition": "Akcesorium / Ignorowane",
                    "is_damaged": False,
                    "damage_details": reason,
                    "face_id_working": None,
                    "icloud_clean": None,
                    "ai_verdict": f"Pominięto: {reason}",
                })
                self.log_event("INFO", f"Filtr heurystyczny: pominięto '{offer['title'][:30]}' ({reason})", idx=olx_id)
                return

            ai_data, _ = ai.analyze_listing(
                title=offer["title"],
                price=offer["price"],
                params_text=params_text,
                description=offer["description"],
                idx=olx_id,
            )

            if self._stop_event.is_set():
                return

            if ai_data:
                db.update_ai_analysis(olx_id, ai_data)
                is_dam = bool(ai_data.get("is_damaged"))
                with self._lock:
                    self.session_metrics["ai_analyzed"] += 1
                    if is_dam:
                        self.session_metrics["damaged"] += 1
                    else:
                        self.session_metrics["healthy"] += 1

                model = ai_data.get("exact_model") or offer["title"][:20]
                bat = f"{ai_data.get('battery_health_pct')}%" if ai_data.get("battery_health_pct") else "?"
                state_lbl = "USZKODZONY" if is_dam else "SPRAWNY"
                self.log_event("SUCCESS", f"Zbadano: {model} | Bat: {bat} | Stan: {state_lbl}", idx=olx_id)

        except Exception as e:
            self.log_event("ERROR", f"Błąd przetwarzania oferty {olx_id}: {e}", idx=olx_id)
        finally:
            with self._lock:
                self.current_offer_title = None

    def _run_single_cycle(
        self,
        pages_count: int,
        threads_count: int,
        scraper: TLSScraper,
        ai: DeepSeekAnalyzer,
        db: Database,
    ) -> None:
        with self._lock:
            self.status_message = "Weryfikacja bazy i sprawdzanie nowych stron..."
            self.current_progress = 0.05
            self.progress_label = "Skanowanie strony 1..."

        all_new_queue: list[tuple[dict[str, Any], str | None]] = []
        seen_ids: set[str] = set()

        # Sprawdzenie zaległych ofert
        pending = db.get_pending_unanalyzed_offers(limit=30)
        if pending:
            self.log_event("SMART", f"Wznawianie {len(pending)} nieprzeanalizowanych ofert z poprzedniej sesji.")
            for p_off in pending:
                seen_ids.add(str(p_off["olx_id"]))
                all_new_queue.append((p_off, None))

        for page in range(1, pages_count + 1):
            if self._stop_event.is_set():
                return

            with self._lock:
                self.status_message = f"Skanowanie strony OLX {page}/{pages_count}..."
                self.current_progress = 0.08 + (0.15 * (page / pages_count))
                self.progress_label = f"Strona {page} z {pages_count}"

            t_start = time.perf_counter()
            status, offers, used_proxy = scraper.fetch_page(page=page)
            duration = time.perf_counter() - t_start

            if status != 200 or not offers:
                self.log_event("WARN", f"Strona {page}: HTTP {status} lub pusta odpowiedź.")
                continue

            page_ids = [str(o["olx_id"]) for o in offers]
            fingerprint = hashlib.md5(",".join(page_ids).encode()).hexdigest()[:12]
            last_fingerprint = db.get_last_page_fingerprint(page)

            new_on_page = 0
            for off in offers:
                oid = str(off["olx_id"])
                if oid in seen_ids or db.offer_exists(oid):
                    with self._lock:
                        self.session_metrics["duplicates_skipped"] += 1
                else:
                    seen_ids.add(oid)
                    all_new_queue.append((off, used_proxy))
                    new_on_page += 1
                    with self._lock:
                        self.session_metrics["total_found"] += 1

            db.record_page_scan(
                page_number=page,
                offers_total=len(offers),
                new_offers=new_on_page,
                fingerprint=fingerprint,
                duration_s=duration,
            )

            # Optymalizacja Early-Stopping
            if page > 1 and new_on_page == 0:
                self.log_event("SMART", f"Granica nowości na stronie {page} (100% duplikatów). Pominięto pozostałe strony.")
                break
            elif page == 1 and last_fingerprint == fingerprint and new_on_page == 0:
                self.log_event("SMART", "Strona 1 identyczna z poprzednim skanem. Brak nowych ogłoszeń na OLX.")
                break

        total_to_process = len(all_new_queue)
        if total_to_process == 0 or self._stop_event.is_set():
            with self._lock:
                self.status_message = "Wszystkie ogłoszenia są aktualne."
                self.current_progress = 1.0
                self.progress_label = "Cykl ukończony"
            return

        with self._lock:
            self.status_message = f"Analiza DeepSeek AI dla {total_to_process} nowych ofert..."
            self.progress_label = f"AI: 0/{total_to_process}"

        completed = 0
        executor = ThreadPoolExecutor(max_workers=threads_count)
        futures = [
            executor.submit(self._process_single_offer, offer, proxy_used, scraper, ai, db)
            for offer, proxy_used in all_new_queue
        ]

        try:
            for _ in as_completed(futures):
                if self._stop_event.is_set():
                    break
                completed += 1
                ratio = 0.25 + (0.75 * (completed / total_to_process))
                with self._lock:
                    self.current_progress = min(1.0, ratio)
                    self.progress_label = f"AI: {completed}/{total_to_process}"
                    self.status_message = f"Analiza ofert DeepSeek AI ({completed}/{total_to_process})..."
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _run_scanning_loop(self, config_override: dict[str, Any] | None = None) -> None:
        try:
            cfg = load_config() or {}
            if config_override:
                cfg.update(config_override)

            api_key = cfg.get("api_key") or os.getenv("DEEPSEEK_API_KEY", "")
            model_name = cfg.get("model", "deepseek-v4-flash-vision-exp")
            ai_lang = cfg.get("ai_language") or cfg.get("language") or "pl"
            pages_count = int(cfg.get("pages", 3))
            threads_count = int(cfg.get("threads", 8))
            watch_mode = bool(cfg.get("watch", False))
            interval_seconds = int(cfg.get("interval", 120))
            region = normalize_region(cfg.get("region"))
            region_label = get_region_display_name(region)

            self.log_event("INFO", f"Obszar: {region_label} | Język AI: {ai_lang.upper()} | Strony: {pages_count} | Tryb: {'Watch' if watch_mode else 'Single'}")

            # Inicjalizacja komponentów
            db = Database(self.db_path)
            ai = DeepSeekAnalyzer(
                api_key=api_key,
                model=model_name,
                language=ai_lang,
                logger=lambda msg, lvl, idx: self.log_event(lvl, msg, idx),
            )
            scraper = TLSScraper(
                static_proxy=cfg.get("custom_proxy"),
                region=region,
                logger=lambda msg, lvl, idx: self.log_event(lvl, msg, idx),
            )

            while not self._stop_event.is_set():
                with self._lock:
                    self.status_code = "running"
                    self.next_scan_seconds = 0

                self._run_single_cycle(
                    pages_count=pages_count,
                    threads_count=threads_count,
                    scraper=scraper,
                    ai=ai,
                    db=db,
                )

                if not watch_mode or self._stop_event.is_set():
                    break

                with self._lock:
                    self.status_code = "waiting"
                    self.status_message = "Oczekiwanie na kolejny cykl skanowania..."
                    self.progress_label = "Pomiędzy cyklami"

                for remaining in range(interval_seconds, 0, -1):
                    if self._stop_event.is_set():
                        break
                    with self._lock:
                        self.next_scan_seconds = remaining
                    time.sleep(1)

                with self._lock:
                    self.current_cycle += 1
                    self.next_scan_seconds = 0

        except Exception as err:
            import traceback
            tb_last = traceback.format_exc().strip().splitlines()[-1]
            self.log_event("ERROR", f"Krytyczny błąd pętli skanera: {err}")
            self.log_event("ERROR", f"Szczegóły: {tb_last}")
            with self._lock:
                self.status_code = "error"
                self.status_message = f"Błąd: {err}"
        finally:
            with self._lock:
                self.is_running = False
                if self.status_code != "error":
                    self.status_code = "idle"
                    self.status_message = "Skaner zakończył działanie (bezczynny)"
                self.current_progress = 0.0
                self.progress_label = "Bezczynny"
                self.current_offer_title = None
            self.log_event("INFO", "Proces skanera został zatrzymany.")
            
# Globalna instancja singletona usługi skanera
scanner_service = ScannerService()