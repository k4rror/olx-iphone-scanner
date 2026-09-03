from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

CONFIG_FILE_PATH = Path("scanner_config.json")


def init_environment() -> None:
    env_candidates = [
        Path(".env"),
        Path(__file__).parent.parent.parent.parent / ".env",
    ]
    for env_path in env_candidates:
        if env_path.is_file():
            load_dotenv(dotenv_path=env_path, override=True)
            break


def load_config() -> dict[str, Any] | None:
    if CONFIG_FILE_PATH.is_file():
        try:
            return json.loads(CONFIG_FILE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def save_config(config: dict[str, Any]) -> None:
    CONFIG_FILE_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")