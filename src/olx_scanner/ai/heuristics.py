from __future__ import annotations

import re

NEGATIVE_TITLE_KEYWORDS = [
    "pudełko", "pudelko", "pudełka", "pudelka", "box", "case", "etui", "obudowa", "szkło", "szklo",
    "pokrowiec", "ładowarka", "ladowarka", "kabel", "sluchawki", "słuchawki", "adapter",
    "doładowanie", "doladowanie", "voucher", "bateria do", "wyswietlacz do", "wyświetlacz do",
    "ekran do", "części do", "czesci do", "korpus", "klapka"
]

ACCESSORY_PREFIXES = (
    "pudełko", "pudelko", "pudełka", "pudelka", "box", "etui", "case", "szkło", "szklo",
    "ładowarka", "ladowarka", "kabel", "doładowanie", "doladowanie", "pokrowiec",
    "ekran", "wyświetlacz", "wyswietlacz", "bateria", "części", "czesci", "szybka",
    "obudowa", "korpus", "klapka", "adapter", "uchwyt", "słuchawki", "sluchawki"
)

NON_APPLE_BRANDS = [
    "samsung", "xiaomi", "redmi", "google pixel", "pixel", "huawei", "motorola",
    "oppo", "realme", "oneplus", "poco", "sony xperia"
]


def is_likely_iphone_offer(title: str, description: str = "", price: float | None = None) -> tuple[bool, str]:
    t_lower = title.lower().strip()
    d_lower = description.lower() if description else ""

    for brand in NON_APPLE_BRANDS:
        if t_lower.startswith(brand):
            return False, f"Inna marka: '{brand}'"

    is_battery_headline = bool(re.match(r"^[#@]?\s*(bateria|kondycja)\s*[:\s]?\s*\d+%", t_lower))
    if t_lower.startswith(ACCESSORY_PREFIXES) and not is_battery_headline:
        return False, "Akcesorium lub część zamienna"

    for kw in ["części do", "czesci do", "ekran do", "wyświetlacz do", "wyswietlacz do", "bateria do", "klapka do"]:
        if kw in t_lower:
            return False, f"Część zamienna: '{kw}'"

    has_model_mention = bool(re.search(r"iphone\s+(\d+|se|x|xr|xs|pro|max|mini)", t_lower))
    for kw in NEGATIVE_TITLE_KEYWORDS:
        if re.search(rf"\b{kw}\b", t_lower):
            if not has_model_mention and not is_battery_headline:
                return False, f"Akcesorium: '{kw}'"
            if t_lower.startswith(("pudełko", "pudelko", "box", "etui", "case", "szkło", "szklo", "ładowarka", "kabel")):
                return False, f"Akcesorium: '{kw}'"

    is_vintage = bool(re.search(r"iphone\s+([4567]|se\s*1|3g)", t_lower))
    min_price_threshold = 50.0 if is_vintage else 100.0
    if (
        price is not None
        and 0 < price < min_price_threshold
        and not any(kw in t_lower for kw in ["uszkodzony", "na części", "blokada", "icloud"])
    ):
        return False, f"Podejrzanie niska cena ({price:.0f} PLN)"

    has_keyword = (
        "iphone" in t_lower or "i phone" in t_lower or "apple" in t_lower or
        "iphone" in d_lower or "i phone" in d_lower
    )
    if not has_keyword:
        return False, "Brak słowa kluczowego 'iPhone'"

    return True, "OK"
