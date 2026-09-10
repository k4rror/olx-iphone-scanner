from __future__ import annotations

import unicodedata

# Oficjalne identyfikatory (slugi) 16 polskich województw na OLX.pl
VOIVODESHIPS: dict[str, str] = {
    "dolnoslaskie": "Dolnośląskie",
    "kujawsko-pomorskie": "Kujawsko-pomorskie",
    "lubelskie": "Lubelskie",
    "lubuskie": "Lubuskie",
    "lodzkie": "Łódzkie",
    "malopolskie": "Małopolskie",
    "mazowieckie": "Mazowieckie",
    "opolskie": "Opolskie",
    "podkarpackie": "Podkarpackie",
    "podlaskie": "Podlaskie",
    "pomorskie": "Pomorskie",
    "slaskie": "Śląskie",
    "swietokrzyskie": "Świętokrzyskie",
    "warminsko-mazurskie": "Warmińsko-mazurskie",
    "wielkopolskie": "Wielkopolskie",
    "zachodniopomorskie": "Zachodniopomorskie",
}

# Aliasy ułatwiające wprowadzanie z CLI i kreatora
REGION_ALIASES: dict[str, str] = {
    "dolny slask": "dolnoslaskie",
    "kujawy": "kujawsko-pomorskie",
    "lodz": "lodzkie",
    "malopolska": "malopolskie",
    "krakow": "malopolskie",
    "mazowsze": "mazowieckie",
    "warszawa": "mazowieckie",
    "slask": "slaskie",
    "katowice": "slaskie",
    "wielkopolska": "wielkopolskie",
    "poznan": "wielkopolskie",
    "pomorze": "pomorskie",
    "gdansk": "pomorskie",
    "warmia": "warminsko-mazurskie",
}


def strip_accents(text: str) -> str:
    """Usuwa polskie znaki diakrytyczne (np. ę -> e, ł -> l, ś -> s)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).replace("ł", "l").replace("Ł", "L")


def normalize_region(region_input: str | None) -> str | None:
    """
    Normalizuje dowolny ciąg wejściowy do poprawnego sluga OLX.
    Zwraca None, jeśli wybrano całą Polskę lub wartość jest pusta/błędna.
    """
    if not region_input:
        return None

    cleaned = strip_accents(region_input.strip().lower())
    if cleaned in ("0", "all", "polska", "cala polska", "none", ""):
        return None

    if cleaned in VOIVODESHIPS:
        return cleaned

    if cleaned in REGION_ALIASES:
        return REGION_ALIASES[cleaned]

    for slug, label in VOIVODESHIPS.items():
        if cleaned in slug or cleaned in strip_accents(label.lower()):
            return slug

    return None


def get_region_display_name(slug: str | None, default_label: str = "Cała Polska") -> str:
    """Zwraca sformatowaną nazwę województwa do prezentacji w TUI i logach."""
    if not slug:
        return default_label
    return VOIVODESHIPS.get(slug, slug.capitalize())