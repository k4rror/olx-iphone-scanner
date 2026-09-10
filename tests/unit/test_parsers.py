from olx_scanner.scraper.client import TLSScraper
from olx_scanner.scraper.parsers import extract_full_offer_data_from_html, link_is_promoted, parse_price
from olx_scanner.scraper.proxy import parse_proxy_line


def test_parse_price():
    assert parse_price("1 850 zł") == 1850.0
    assert parse_price("2.499,99 zł") == 2499.99
    assert parse_price("Za darmo") == 0.0
    assert parse_price("Cena do negocjacji") is None


def test_parse_proxy_line():
    parsed = parse_proxy_line("178.212.144.7:80")
    assert parsed is not None
    assert parsed["host"] == "178.212.144.7"
    assert parsed["port"] == 80


def test_html_offer_extraction(sample_html_offer):
    data = extract_full_offer_data_from_html(sample_html_offer)
    assert data["price"] == 2150.0
    assert "128 GB" in data["params_text"]
    assert "89%" in data["description"]


def test_link_is_promoted():
    # Promowane (zakodowane %7C oraz czyste |)
    assert link_is_promoted("/d/oferta/iphone-13.html?search_reason=search%7Cpromoted")
    assert link_is_promoted("https://www.olx.pl/d/oferta/iphone-13.html?search_reason=search%7Cpromoted")
    assert link_is_promoted("/d/oferta/iphone-13.html?other=1&search_reason=search%7CPromoted")
    # Organiczne / brak parametru / puste
    assert not link_is_promoted("/d/oferta/iphone-15.html?search_reason=search%7Corganic")
    assert not link_is_promoted("/d/oferta/iphone-15.html")
    assert not link_is_promoted("")


_LISTING_HTML = """
<div id="1" data-cy="l-card">
  <a data-testid="card-title-link" href="/d/oferta/iphone-13-mini.html?search_reason=search%7Cpromoted">iPhone 13 mini</a>
</div>
<div id="2" data-cy="l-card">
  <a data-testid="card-title-link" href="/d/oferta/iphone-15-pro.html?search_reason=search%7Corganic">iPhone 15 Pro</a>
</div>
<div id="3" data-cy="l-card">
  <a data-testid="card-title-link" href="/d/oferta/iphone-15.html?extra=1">iPhone 15</a>
</div>
<div data-testid="qa-advert-slot" data-cy="baxter-slot-div-gpt-ad-listing-sponsored-ad-first">
  <div data-cy="l-card">
    <a data-testid="card-title-link" href="https://reklamodawca.example/landing">Zewnętrzna reklama</a>
  </div>
</div>
"""


def test_parse_html_cards_skips_promoted_and_ad_slots():
    scraper = TLSScraper()
    offers = scraper._parse_html_cards(_LISTING_HTML)
    urls = [o["url"] for o in offers]
    assert urls == [
        "https://www.olx.pl/d/oferta/iphone-15-pro.html",
        "https://www.olx.pl/d/oferta/iphone-15.html",
    ]
