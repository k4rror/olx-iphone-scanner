from __future__ import annotations

from typing import Any

# =============================================================================
# PARAMETRY ZAPYTAŃ I TOKENÓW (deepseek-v4-flash-vision-exp)
# =============================================================================
AVERAGE_INPUT_CACHE_HIT_TOKENS: int = 270    # Stały prompt systemowy (Context Cache)
AVERAGE_INPUT_CACHE_MISS_TOKENS: int = 220   # Unikalna treść ogłoszenia
AVERAGE_OUTPUT_TOKENS: int = 110             # Schemat JSON IPhoneAnalysis
AVERAGE_TOTAL_TOKENS: int = 600              # Średnia całkowita z logów sesji

ITEMS_PER_PAGE: int = 52
USD_TO_PLN_RATE: float = 4.00

# =============================================================================
# KOSZT JEDNEGO OGŁOSZENIA (w USD)
# =============================================================================
# Wariant A: Godziny szczytu (Peak) z działającym Cache dla promptu systemowego
# 270 * $0.000000014 + 220 * $0.00000044 + 110 * $0.00000132 = $0.00024578
COST_PER_OFFER_STANDARD_USD: float = 0.00024578

# Wariant B: Godziny pozaszczytowe (Off-Peak) z Cache (najbardziej optymistyczny)
# 270 * $0.000000007 + 220 * $0.00000022 + 110 * $0.00000066 = $0.00012289
COST_PER_OFFER_OFFPEAK_USD: float = 0.00012289

# Wariant C: Godziny szczytu (Peak) przy 100% Cache Miss (pesymistyczny)
# 490 * $0.00000044 + 110 * $0.00000132 = $0.00036080
COST_PER_OFFER_PESSIMISTIC_USD: float = 0.00036080

# =============================================================================
# KOSZT 1 STRONY OLX (52 ogłoszenia)
# =============================================================================
COST_PER_PAGE_STANDARD_USD: float = ITEMS_PER_PAGE * COST_PER_OFFER_STANDARD_USD   # ~$0.0128 USD
COST_PER_PAGE_OFFPEAK_USD: float = ITEMS_PER_PAGE * COST_PER_OFFER_OFFPEAK_USD     # ~$0.0064 USD
COST_PER_PAGE_PESSIMISTIC_USD: float = ITEMS_PER_PAGE * COST_PER_OFFER_PESSIMISTIC_USD # ~$0.0188 USD


def calculate_deepseek_cost(offers_count: int) -> dict[str, Any]:
    """
    Kalkuluje precyzyjny koszt DeepSeek API dla zadanego wolumenu ogłoszeń.
    Zwraca estymację standardową (Wariant A) oraz widełki min-max (Wariant B - C).
    """
    safe_count = max(0, offers_count)

    standard_usd = safe_count * COST_PER_OFFER_STANDARD_USD
    offpeak_usd = safe_count * COST_PER_OFFER_OFFPEAK_USD
    pessimistic_usd = safe_count * COST_PER_OFFER_PESSIMISTIC_USD

    return {
        "offers_count": safe_count,
        "standard_usd": round(standard_usd, 4),
        "standard_pln": round(standard_usd * USD_TO_PLN_RATE, 4),
        "offpeak_usd": round(offpeak_usd, 4),
        "offpeak_pln": round(offpeak_usd * USD_TO_PLN_RATE, 4),
        "pessimistic_usd": round(pessimistic_usd, 4),
        "pessimistic_pln": round(pessimistic_usd * USD_TO_PLN_RATE, 4),
    }