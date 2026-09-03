from olx_scanner.scraper.parsers import extract_full_offer_data_from_html, parse_price
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