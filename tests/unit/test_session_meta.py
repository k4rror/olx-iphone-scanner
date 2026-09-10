import pytest

from olx_scanner.core.pricing import (
    COST_PER_OFFER_OFFPEAK_USD,
    COST_PER_OFFER_PESSIMISTIC_USD,
    COST_PER_OFFER_STANDARD_USD,
    COST_PER_PAGE_STANDARD_USD,
    ITEMS_PER_PAGE,
    calculate_deepseek_cost,
)
from olx_scanner.scraper.parsers import extract_search_page_meta


def test_extract_search_page_meta_with_regex():
    html_mock = """
    <html>
        <body>
            <div data-testid="search-results-title">
                <h1>Znaleźliśmy 1 560 ogłoszeń</h1>
            </div>
            <div data-cy="l-card" id="1"></div>
            <div data-cy="l-card" id="2"></div>
        </body>
    </html>
    """
    total_items, total_pages = extract_search_page_meta(html_mock)
    assert total_items == 1560
    assert total_pages == 25


def test_deepseek_cost_calculation_per_offer():
    # 1 ogłoszenie
    c1 = calculate_deepseek_cost(1)
    assert c1["standard_usd"] == 0.0002
    assert c1["offpeak_usd"] == 0.0001
    assert c1["pessimistic_usd"] == 0.0004
    assert round(c1["standard_pln"], 4) == 0.0010


def test_deepseek_cost_calculation_per_page():
    # 1 strona = 52 ogłoszenia
    cp = calculate_deepseek_cost(ITEMS_PER_PAGE)
    # 52 * 0.00024578 = 0.01278 USD (~0.051 zł)
    assert 0.012 <= cp["standard_usd"] <= 0.013
    assert 0.050 <= cp["standard_pln"] <= 0.052
    # Widełki: 0.006 USD (Off-Peak) do 0.019 USD (Peak 100% Miss)
    assert 0.006 <= cp["offpeak_usd"] <= 0.007
    assert 0.018 <= cp["pessimistic_usd"] <= 0.019


def test_deepseek_cost_macro_scale():
    # 1 000 ogłoszeń: $0.12 – $0.36 USD (~0.49 zł – 1.44 zł)
    c1000 = calculate_deepseek_cost(1000)
    assert round(c1000["offpeak_usd"], 2) == 0.12
    assert round(c1000["standard_usd"], 2) == 0.25
    assert round(c1000["pessimistic_usd"], 2) == 0.36
    assert round(c1000["offpeak_pln"], 2) == 0.49
    assert round(c1000["pessimistic_pln"], 2) == 1.44