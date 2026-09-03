from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from pydantic import BaseModel, Field, field_validator


class IPhoneAnalysis(BaseModel):
    exact_model: str | None = Field(default=None, description="Dokładny model, np. iPhone 13 Pro")
    storage_gb: int | None = Field(default=None, description="Pojemność pamięci w GB")
    color: str | None = Field(default=None, description="Kolor obudowy")
    battery_health_pct: int | None = Field(default=None, description="Kondycja baterii w %")
    condition: str | None = Field(default=None, description="Stan wizualny i techniczny")
    is_damaged: bool = Field(default=False, description="Czy telefon jest uszkodzony")
    damage_details: str | None = Field(default=None, description="Szczegóły ewentualnych uszkodzeń")
    face_id_working: bool | None = Field(default=None, description="Czy Face ID jest sprawne")
    icloud_clean: bool | None = Field(default=None, description="Czy brak blokady iCloud")
    ai_verdict: str | None = Field(default=None, description="Zwięzłe 1-zdaniowe podsumowanie stanu")

    @field_validator("storage_gb", "battery_health_pct", mode="before")
    @classmethod
    def parse_numeric(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            val = int(v)
            return val if val > 0 else None
        if isinstance(v, str):
            m = re.search(r"\d+", v)
            return int(m.group(0)) if m else None
        return None

    @field_validator("is_damaged", mode="before")
    @classmethod
    def parse_bool_damaged(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "tak", "yes", "1", "uszkodzony", "ja", "так", "пашкоджаны")
        return False


@dataclass(slots=True)
class VerifiedProxy:
    url: str
    kind: str
    addr: str
    latency_ms: int
    fails: int = 0