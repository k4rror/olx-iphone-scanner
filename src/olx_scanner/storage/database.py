from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
        """Zarządca kontekstu zapewniający automatyczne zwalnianie blokad SQLite."""
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

            cursor = conn.execute("PRAGMA table_info(iphone_offers)")
            existing_cols = {row["name"] for row in cursor.fetchall()}

            if "is_favorite" not in existing_cols:
                conn.execute("ALTER TABLE iphone_offers ADD COLUMN is_favorite INTEGER DEFAULT 0")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_is_favorite ON iphone_offers(is_favorite)")

            if "user_notes" not in existing_cols:
                conn.execute("ALTER TABLE iphone_offers ADD COLUMN user_notes TEXT DEFAULT ''")

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
            favorites = conn.execute("SELECT COUNT(*) FROM iphone_offers WHERE is_favorite = 1").fetchone()[0]
            return {
                "total": total,
                "analyzed": analyzed,
                "damaged": damaged,
                "pages_scanned": pages_scanned,
                "favorites": favorites,
            }

    # =========================================================================
    # METODY ZARZĄDZANIA DANYMI I ZAAWANSOWANEGO ODCZYTU (W TYM MARŻA)
    # =========================================================================

    def query_offers(
        self,
        q: str | None = None,
        model: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        min_battery: int | None = None,
        max_battery: int | None = None,
        storage: int | None = None,
        is_damaged: bool | None = None,
        face_id_working: bool | None = None,
        icloud_clean: bool | None = None,
        is_favorite: bool | None = None,
        only_analyzed: bool = False,
        min_margin: float | None = None,
        only_deals: bool = False,
        sort_by: str = "newest",
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        """Pobiera przefiltrowaną listę ofert z wyliczeniem marży rynkowej i paginacją."""
        conditions: list[str] = []
        params: list[Any] = []

        if q and q.strip():
            query_str = f"%{q.strip()}%"
            conditions.append(
                "(title LIKE ? OR description LIKE ? OR ai_summary LIKE ? OR model_name LIKE ? OR location LIKE ?)"
            )
            params.extend([query_str, query_str, query_str, query_str, query_str])

        if model and model.strip() and model != "ALL":
            conditions.append("model_name = ?")
            params.append(model.strip())

        if min_price is not None:
            conditions.append("price >= ?")
            params.append(min_price)

        if max_price is not None:
            conditions.append("price <= ?")
            params.append(max_price)

        if min_battery is not None:
            conditions.append("battery_health_pct >= ?")
            params.append(min_battery)

        if max_battery is not None:
            conditions.append("battery_health_pct <= ?")
            params.append(max_battery)

        if storage is not None:
            conditions.append("storage_gb = ?")
            params.append(storage)

        if is_damaged is not None:
            conditions.append("is_damaged = ?")
            params.append(1 if is_damaged else 0)

        if face_id_working is not None:
            conditions.append("face_id_working = ?")
            params.append(1 if face_id_working else 0)

        if icloud_clean is not None:
            conditions.append("icloud_clean = ?")
            params.append(1 if icloud_clean else 0)

        if is_favorite is not None:
            conditions.append("is_favorite = ?")
            params.append(1 if is_favorite else 0)

        if only_analyzed:
            conditions.append("ai_analyzed = 1")

        if min_margin is not None:
            conditions.append("margin_pln >= ?")
            params.append(min_margin)

        if only_deals:
            conditions.append("margin_pln > 0")

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        sort_map = {
            "newest": "id DESC",
            "oldest": "id ASC",
            "price_asc": "CASE WHEN price IS NULL THEN 1 ELSE 0 END, price ASC",
            "price_desc": "CASE WHEN price IS NULL THEN 1 ELSE 0 END, price DESC",
            "battery_desc": "CASE WHEN battery_health_pct IS NULL THEN 1 ELSE 0 END, battery_health_pct DESC",
            "margin_desc": "CASE WHEN margin_pln IS NULL THEN 1 ELSE 0 END, margin_pln DESC, id DESC",
            "margin_pct_desc": "CASE WHEN margin_pct IS NULL THEN 1 ELSE 0 END, margin_pct DESC, id DESC",
            "scraped_desc": "scraped_at DESC",
        }
        order_clause = sort_map.get(sort_by, "id DESC")

        base_cte = """
            WITH model_stats AS (
                SELECT 
                    model_name,
                    ROUND(COALESCE(
                        AVG(CASE WHEN (is_damaged = 0 OR is_damaged IS NULL) AND price > 0 THEN price END),
                        AVG(CASE WHEN price > 0 THEN price END)
                    ), 0) AS avg_model_price,
                    COUNT(CASE WHEN price > 0 THEN 1 END) AS model_offers_count
                FROM iphone_offers
                WHERE model_name IS NOT NULL AND model_name != '' AND price > 0 AND ai_analyzed = 1
                GROUP BY model_name
            ),
            enriched_offers AS (
                SELECT 
                    o.*,
                    m.avg_model_price,
                    m.model_offers_count,
                    CASE 
                        WHEN o.price > 0 AND m.avg_model_price > 0 
                        THEN ROUND(m.avg_model_price - o.price, 0)
                        ELSE NULL 
                    END AS margin_pln,
                    CASE 
                        WHEN o.price > 0 AND m.avg_model_price > 0 
                        THEN ROUND(((m.avg_model_price - o.price) * 100.0) / m.avg_model_price, 1)
                        ELSE NULL 
                    END AS margin_pct
                FROM iphone_offers o
                LEFT JOIN model_stats m ON o.model_name = m.model_name
            )
        """

        with self._get_conn() as conn:
            count_sql = f"{base_cte} SELECT COUNT(*) FROM enriched_offers {where_clause}"
            total_items = conn.execute(count_sql, params).fetchone()[0]

            safe_page = max(1, page)
            safe_page_size = max(1, min(page_size, 200))
            offset = (safe_page - 1) * safe_page_size
            total_pages = math.ceil(total_items / safe_page_size) if total_items > 0 else 1

            query_sql = f"""
                {base_cte}
                SELECT * FROM enriched_offers
                {where_clause}
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
            """
            data_params = list(params) + [safe_page_size, offset]
            rows = conn.execute(query_sql, data_params).fetchall()

            return {
                "items": [dict(r) for r in rows],
                "total": total_items,
                "page": safe_page,
                "page_size": safe_page_size,
                "total_pages": total_pages,
            }

    def get_offer_by_id(self, olx_id: str) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            sql = """
                WITH model_stats AS (
                    SELECT 
                        model_name,
                        ROUND(COALESCE(
                            AVG(CASE WHEN (is_damaged = 0 OR is_damaged IS NULL) AND price > 0 THEN price END),
                            AVG(CASE WHEN price > 0 THEN price END)
                        ), 0) AS avg_model_price,
                        COUNT(CASE WHEN price > 0 THEN 1 END) AS model_offers_count
                    FROM iphone_offers
                    WHERE model_name IS NOT NULL AND model_name != '' AND price > 0 AND ai_analyzed = 1
                    GROUP BY model_name
                ),
                enriched_offers AS (
                    SELECT 
                        o.*,
                        m.avg_model_price,
                        m.model_offers_count,
                        CASE 
                            WHEN o.price > 0 AND m.avg_model_price > 0 
                            THEN ROUND(m.avg_model_price - o.price, 0)
                            ELSE NULL 
                        END AS margin_pln,
                        CASE 
                            WHEN o.price > 0 AND m.avg_model_price > 0 
                            THEN ROUND(((m.avg_model_price - o.price) * 100.0) / m.avg_model_price, 1)
                            ELSE NULL 
                        END AS margin_pct
                    FROM iphone_offers o
                    LEFT JOIN model_stats m ON o.model_name = m.model_name
                )
                SELECT * FROM enriched_offers WHERE olx_id = ?
            """
            cursor = conn.execute(sql, (str(olx_id),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_offer(self, olx_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM iphone_offers WHERE olx_id = ?", (str(olx_id),))
            conn.commit()
            return cursor.rowcount > 0

    def toggle_favorite(self, olx_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                UPDATE iphone_offers 
                SET is_favorite = CASE WHEN is_favorite = 1 THEN 0 ELSE 1 END
                WHERE olx_id = ?
                """,
                (str(olx_id),),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return False

            res = conn.execute("SELECT is_favorite FROM iphone_offers WHERE olx_id = ?", (str(olx_id),)).fetchone()
            return bool(res and res["is_favorite"] == 1)

    def update_notes(self, olx_id: str, notes: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE iphone_offers SET user_notes = ? WHERE olx_id = ?",
                (notes, str(olx_id)),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_distinct_models(self) -> list[str]:
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT model_name 
                FROM iphone_offers 
                WHERE model_name IS NOT NULL AND model_name != ''
                ORDER BY model_name ASC
            """)
            return [row["model_name"] for row in cursor.fetchall()]

    def get_analytics_summary(self) -> dict[str, Any]:
        with self._get_conn() as conn:
            models_stats = conn.execute("""
                SELECT 
                    model_name,
                    COUNT(*) as count,
                    ROUND(AVG(price), 0) as avg_price,
                    ROUND(MIN(price), 0) as min_price,
                    ROUND(MAX(price), 0) as max_price
                FROM iphone_offers 
                WHERE ai_analyzed = 1 AND model_name IS NOT NULL AND price > 0
                GROUP BY model_name
                HAVING count >= 1
                ORDER BY count DESC, avg_price DESC
                LIMIT 15
            """).fetchall()

            battery_stats = conn.execute("""
                SELECT
                    SUM(CASE WHEN battery_health_pct >= 90 THEN 1 ELSE 0 END) as bat_90_100,
                    SUM(CASE WHEN battery_health_pct >= 85 AND battery_health_pct < 90 THEN 1 ELSE 0 END) as bat_85_89,
                    SUM(CASE WHEN battery_health_pct >= 80 AND battery_health_pct < 85 THEN 1 ELSE 0 END) as bat_80_84,
                    SUM(CASE WHEN battery_health_pct < 80 THEN 1 ELSE 0 END) as bat_below_80,
                    SUM(CASE WHEN battery_health_pct IS NULL AND ai_analyzed = 1 THEN 1 ELSE 0 END) as bat_unknown
                FROM iphone_offers
            """).fetchone()

            condition_stats = conn.execute("""
                SELECT
                    SUM(CASE WHEN is_damaged = 0 AND ai_analyzed = 1 THEN 1 ELSE 0 END) as healthy,
                    SUM(CASE WHEN is_damaged = 1 THEN 1 ELSE 0 END) as damaged,
                    SUM(CASE WHEN ai_analyzed = 0 THEN 1 ELSE 0 END) as pending
                FROM iphone_offers
            """).fetchone()

            price_kpi = conn.execute("""
                SELECT 
                    ROUND(AVG(price), 0) as avg_price,
                    ROUND(MIN(price), 0) as min_price,
                    ROUND(MAX(price), 0) as max_price
                FROM iphone_offers
                WHERE price > 0
            """).fetchone()

            return {
                "models_price": [dict(r) for r in models_stats],
                "battery_distribution": dict(battery_stats) if battery_stats else {},
                "condition_distribution": dict(condition_stats) if condition_stats else {},
                "price_kpi": dict(price_kpi) if price_kpi else {"avg_price": 0, "min_price": 0, "max_price": 0},
            }

    def get_model_stats(self, model_name: str | None = None) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            if model_name:
                cursor = conn.execute(
                    """
                    SELECT 
                        model_name,
                        COUNT(*) as total_count,
                        ROUND(AVG(CASE WHEN price > 0 THEN price END), 0) as avg_price,
                        ROUND(MIN(CASE WHEN price > 0 THEN price END), 0) as min_price,
                        ROUND(MAX(CASE WHEN price > 0 THEN price END), 0) as max_price,
                        ROUND(AVG(CASE WHEN battery_health_pct > 0 THEN battery_health_pct END), 1) as avg_battery,
                        SUM(CASE WHEN is_damaged = 1 THEN 1 ELSE 0 END) as damaged_count,
                        SUM(CASE WHEN is_damaged = 0 AND ai_analyzed = 1 THEN 1 ELSE 0 END) as healthy_count
                    FROM iphone_offers 
                    WHERE model_name = ?
                    GROUP BY model_name
                    """,
                    (model_name,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
            else:
                cursor = conn.execute(
                    """
                    SELECT 
                        model_name,
                        COUNT(*) as total_count,
                        ROUND(AVG(CASE WHEN price > 0 THEN price END), 0) as avg_price,
                        ROUND(MIN(CASE WHEN price > 0 THEN price END), 0) as min_price,
                        ROUND(MAX(CASE WHEN price > 0 THEN price END), 0) as max_price,
                        ROUND(AVG(CASE WHEN battery_health_pct > 0 THEN battery_health_pct END), 1) as avg_battery,
                        SUM(CASE WHEN is_damaged = 1 THEN 1 ELSE 0 END) as damaged_count,
                        SUM(CASE WHEN is_damaged = 0 AND ai_analyzed = 1 THEN 1 ELSE 0 END) as healthy_count
                    FROM iphone_offers 
                    WHERE model_name IS NOT NULL AND model_name != ''
                    GROUP BY model_name
                    """
                )
                return {row["model_name"]: dict(row) for row in cursor.fetchall()}