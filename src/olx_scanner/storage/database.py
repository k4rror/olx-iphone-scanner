# src/olx_scanner/storage/database.py
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Generator


class Database:
    def __init__(
        self,
        db_path: str | Path = "olx_iphones.db",
        logger: Callable[[str, str, str | None], None] | None = None,
    ) -> None:
        self.db_path = str(db_path)
        self.log = logger or (lambda msg, lvl="DB", idx=None: None)
        self._init_db()

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Zarządca kontekstu gwarantujący natychmiastowe zamykanie połączenia."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS iphone_offers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    olx_id TEXT UNIQUE NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    price REAL,
                    currency TEXT DEFAULT 'PLN',
                    location TEXT,
                    posted_at TEXT,
                    description TEXT,
                    scraped_at TEXT NOT NULL,
                    ai_analyzed INTEGER DEFAULT 0,
                    model_name TEXT,
                    storage_gb INTEGER,
                    color TEXT,
                    battery_health_pct INTEGER,
                    condition_state TEXT,
                    is_damaged INTEGER,
                    damage_details TEXT,
                    face_id_working INTEGER,
                    icloud_clean INTEGER,
                    ai_summary TEXT,
                    ai_raw_json TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_olx_id ON iphone_offers(olx_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analyzed_id ON iphone_offers(ai_analyzed, id DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_is_damaged ON iphone_offers(is_damaged)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS scanned_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_number INTEGER NOT NULL,
                    scanned_at TEXT NOT NULL,
                    offers_total INTEGER NOT NULL,
                    new_offers INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    duration_s REAL DEFAULT 0.0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_page_num_date ON scanned_pages(page_number, scanned_at DESC)")
            conn.commit()

    def offer_exists(self, olx_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT 1 FROM iphone_offers WHERE olx_id = ?", (str(olx_id),))
            return cursor.fetchone() is not None

    def is_already_analyzed(self, olx_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT ai_analyzed FROM iphone_offers WHERE olx_id = ?", (str(olx_id),))
            row = cursor.fetchone()
            return bool(row and row["ai_analyzed"] == 1)

    def insert_raw_offer(self, offer: dict[str, Any]) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO iphone_offers (
                        olx_id, url, title, price, currency, location, posted_at, description, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(offer["olx_id"]),
                        offer["url"],
                        offer["title"],
                        offer.get("price"),
                        offer.get("currency", "PLN"),
                        offer.get("location", ""),
                        offer.get("posted_at", ""),
                        offer.get("description", ""),
                        now,
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def update_ai_analysis(self, olx_id: str, ai_data: dict[str, Any]) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE iphone_offers SET
                    ai_analyzed = 1,
                    model_name = ?,
                    storage_gb = ?,
                    color = ?,
                    battery_health_pct = ?,
                    condition_state = ?,
                    is_damaged = ?,
                    damage_details = ?,
                    face_id_working = ?,
                    icloud_clean = ?,
                    ai_summary = ?,
                    ai_raw_json = ?
                WHERE olx_id = ?
                """,
                (
                    ai_data.get("exact_model"),
                    ai_data.get("storage_gb"),
                    ai_data.get("color"),
                    ai_data.get("battery_health_pct"),
                    ai_data.get("condition"),
                    1 if ai_data.get("is_damaged") else 0,
                    ai_data.get("damage_details"),
                    1 if ai_data.get("face_id_working") is True else (0 if ai_data.get("face_id_working") is False else None),
                    1 if ai_data.get("icloud_clean") is True else (0 if ai_data.get("icloud_clean") is False else None),
                    ai_data.get("ai_verdict"),
                    json.dumps(ai_data, ensure_ascii=False),
                    str(olx_id),
                ),
            )
            conn.commit()

    def record_page_scan(
        self,
        page_number: int,
        offers_total: int,
        new_offers: int,
        fingerprint: str,
        duration_s: float = 0.0,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO scanned_pages (page_number, scanned_at, offers_total, new_offers, fingerprint, duration_s)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (page_number, now, offers_total, new_offers, fingerprint, round(duration_s, 2)),
            )
            conn.commit()

    def get_last_page_fingerprint(self, page_number: int) -> str | None:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT fingerprint FROM scanned_pages WHERE page_number = ? ORDER BY id DESC LIMIT 1",
                (page_number,),
            )
            row = cursor.fetchone()
            return row["fingerprint"] if row else None

    def get_pending_unanalyzed_offers(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT olx_id, url, title, price, currency, location, posted_at, description
                FROM iphone_offers 
                WHERE ai_analyzed = 0 
                ORDER BY id ASC LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_analyzed(self, limit: int = 15) -> list[sqlite3.Row]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM iphone_offers 
                WHERE ai_analyzed = 1 
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()

    def get_stats(self) -> dict[str, int]:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM iphone_offers").fetchone()[0]
            analyzed = conn.execute("SELECT COUNT(*) FROM iphone_offers WHERE ai_analyzed = 1").fetchone()[0]
            damaged = conn.execute("SELECT COUNT(*) FROM iphone_offers WHERE is_damaged = 1").fetchone()[0]
            pages_scanned = conn.execute("SELECT COUNT(*) FROM scanned_pages").fetchone()[0]
            return {
                "total": total,
                "analyzed": analyzed,
                "damaged": damaged,
                "pages_scanned": pages_scanned,
            }