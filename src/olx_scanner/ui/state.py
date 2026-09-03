from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import re
import threading
import time
from typing import Any

ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class ActivityEvent:
    timestamp: str
    level: str
    message: str
    idx: str | None = None


@dataclass
class DashboardState:
    model_name: str = "DeepSeek"
    proxy_count: int = 0
    total_offers_db: int = 0
    analyzed_offers_db: int = 0
    damaged_offers_db: int = 0
    healthy_offers_db: int = 0
    smart_skipped_duplicates: int = 0
    pages_scanned_count: int = 0
    early_stopping_active: bool = False
    current_status: str = ""
    current_progress: float = 0.0
    progress_label: str = ""
    cycle_index: int = 1
    next_scan_seconds: int = 0
    recent_events: deque[ActivityEvent] = field(default_factory=lambda: deque(maxlen=4))
    table_rows: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def add_event(self, level: str, msg: str, idx: str | None = None) -> None:
        clean_msg = ANSI_REGEX.sub("", msg)
        ts = time.strftime("%H:%M:%S")
        with self.lock:
            self.recent_events.append(ActivityEvent(timestamp=ts, level=level, message=clean_msg, idx=idx))

    def set_progress(self, progress: float, label: str) -> None:
        with self.lock:
            self.current_progress = max(0.0, min(1.0, progress))
            self.progress_label = label

    def set_status(self, status: str) -> None:
        with self.lock:
            self.current_status = status