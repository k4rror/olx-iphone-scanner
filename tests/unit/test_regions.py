import pytest

from olx_scanner.core.regions import get_region_display_name, normalize_region
from olx_scanner.scraper.client import TLSScraper


@pytest.mark.parametrize(
    ("raw_input", "expected_slug"),
    [
        ("mazowieckie", "mazowieckie"),
        ("Mazowieckie", "mazowieckie"),
        ("śląskie", "slaskie"),
        ("Śląsk", "slaskie"),
        ("lodzkie", "lodzkie"),
        ("Łódzkie", "lodzkie"),
        ("małopolskie", "malopolskie"),
        ("Wielkopolskie", "wielkopolskie"),
        ("0", None),
        ("all", None),
        ("polska", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_region(raw_input: str | None, expected_slug: str | None):
    assert normalize_region(raw_input) == expected_slug


def test_get_region_display_name():
    assert get_region_display_name("mazowieckie") == "Mazowieckie"
    assert get_region_display_name("slaskie") == "Śląskie"
    assert get_region_display_name(None, default_label="Polska") == "Polska"


def test_scraper_search_url_generation():
    # 1. Cała Polska
    scraper_all = TLSScraper(region=None)
    url_p1 = scraper_all.get_search_url(page=1)
    url_p2 = scraper_all.get_search_url(page=2)
    assert url_p1 == "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/q-iphone/?search%5Border%5D=created_at%3Adesc"
    assert url_p2 == "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/q-iphone/?page=2&search%5Border%5D=created_at%3Adesc"

    # 2. Wybrane województwo (np. mazowieckie)
    scraper_region = TLSScraper(region="mazowieckie")
    r_url_p1 = scraper_region.get_search_url(page=1)
    r_url_p2 = scraper_region.get_search_url(page=2)
    assert r_url_p1 == "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/mazowieckie/q-iphone/?search%5Border%5D=created_at%3Adesc"
    assert r_url_p2 == "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/mazowieckie/q-iphone/?page=2&search%5Border%5D=created_at%3Adesc"