from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("\xa0", " ").replace("\r", "")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def parse_price(raw_text: str) -> float | None:
    if not raw_text:
        return None
    text = raw_text.replace("\xa0", " ").strip()
    if any(kw in text.lower() for kw in ["za darmo", "oddam", "darmo"]):
        return 0.0
    m = re.search(r"(\d[\d\s.,]*)", text)
    if not m:
        return None
    num_str = re.sub(r"\s+", "", m.group(1).strip())
    if not num_str:
        return None

    if "," in num_str and "." in num_str:
        last_comma = num_str.rfind(",")
        last_dot = num_str.rfind(".")
        if last_comma > last_dot:
            num_str = num_str.replace(".", "").replace(",", ".")
        else:
            num_str = num_str.replace(",", "")
    elif "," in num_str:
        parts = num_str.split(",")
        num_str = parts[0] + parts[1] if len(parts[1]) == 3 else parts[0] + "." + parts[1]
    elif "." in num_str:
        parts = num_str.split(".")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            num_str = parts[0] + "." + parts[1]
        else:
            num_str = "".join(parts)

    try:
        return float(num_str)
    except ValueError:
        return None


def link_is_promoted(href: str) -> bool:
    """
    Czy link ogłoszenia z listy OLX prowadzi do oferty sponsorowanej / „Wyróżnione”.

    OLX oznacza linki parametrem ``search_reason``:
      * ``search|promoted`` — ogłoszenie promowane (płatne),
      * ``search|organic``  — wynik naturalny.

    W HTML parametr bywa zakodowany procentowo (``search%7Cpromoted``), dlatego
    wartość jest parsowana przez ``parse_qs``. Brak parametru traktujemy jako
    ogłoszenie organiczne — nie pomijamy bez dowodu.
    """
    if not href:
        return False
    query = urlsplit(href).query
    if not query:
        return False
    reasons = parse_qs(query).get("search_reason", [])
    return any("promoted" in reason.lower() for reason in reasons)


def extract_search_page_meta(html_text: str) -> tuple[int, int]:
    """
    Ekstraktuje całkowitą liczbę ogłoszeń oraz łączną liczbę stron dla zapytania.
    Zwraca krotkę: (total_items, total_pages).
    """
    if not html_text:
        return 0, 1

    soup = BeautifulSoup(html_text, "html.parser")
    total_items: int | None = None

    # 1. Sprawdzenie JSON-a stanu osadzonego w skryptach strony
    for script in soup.find_all("script"):
        content = script.string or ""
        if "total_elements" in content or "totalElements" in content:
            m = re.search(r'"total_?elements":\s*(\d+)', content, re.IGNORECASE)
            if m:
                total_items = int(m.group(1))
                break

    # 2. Selektory specyficzne dla OLX (np. data-testid="total-count")
    if total_items is None:
        total_elem = soup.find(attrs={"data-testid": "total-count"}) or soup.find(attrs={"data-cy": "total-count"})
        if total_elem:
            raw_text = total_elem.get_text()
            nums = re.findall(r"\d+", raw_text.replace("\xa0", "").replace(" ", ""))
            if nums:
                total_items = int(nums[0])

    # 3. Fallback regex w treści strony (np. "Znaleźliśmy 1 458 ogłoszeń")
    if total_items is None:
        m = re.search(r"(?:znaleźliśmy|znaleziono|mamy)\s+(?:ponad\s+)?([\d\s\xa0]+)\s+ogłosze", html_text, re.IGNORECASE)
        if m:
            clean_digits = re.sub(r"\D", "", m.group(1))
            if clean_digits:
                total_items = int(clean_digits)

    # 4. Fallback ostateczny: liczba kart ogłoszeń na bieżącej stronie
    if total_items is None:
        cards = soup.find_all("div", attrs={"data-cy": "l-card"})
        total_items = len(cards)

    # Obliczenie liczby stron na podstawie standardu OLX (52 ogłoszenia na stronę)
    computed_pages = max(1, math.ceil(total_items / 52)) if total_items > 0 else 1

    # Weryfikacja z linkami paginacji w HTML
    max_page_in_html = 1
    for a in soup.find_all("a", attrs={"data-cy": re.compile(r"page-link")}):
        txt = a.get_text(strip=True)
        if txt.isdigit():
            max_page_in_html = max(max_page_in_html, int(txt))

    total_pages = max(computed_pages, max_page_in_html)
    # OLX ogranicza paginację dla zapytań do maksymalnie 25 stron
    total_pages = min(total_pages, 25)

    return total_items, total_pages


def extract_full_offer_data_from_html(
    html_text: str,
    logger: Callable[[str, str, str | None], None] | None = None,
    idx: str | None = None,
) -> dict[str, Any]:
    result = {"price": None, "params_text": "", "description": "", "posted_at": "", "location": ""}
    if not html_text:
        return result

    soup = BeautifulSoup(html_text, "html.parser")

    price_box = (
        soup.find("div", attrs={"data-testid": "ad-price-container"})
        or soup.find("div", attrs={"data-testid": "priceBlock"})
        or soup.find("span", attrs={"data-testid": "ad-price"})
    )
    if price_box:
        price_p = price_box.find("p", attrs={"data-nx-name": "P1"}) or price_box
        result["price"] = parse_price(price_p.get_text(strip=True))

    params: list[str] = []
    for span in soup.find_all(["span", "p", "div"], attrs={"data-nx-name": "P3"}):
        txt = span.get_text(strip=True)
        if (
            ":" in txt
            and len(txt) < 80
            and not txt.startswith("Zwróć")
            and not txt.startswith("Więcej")
            and txt not in params
        ):
            params.append(txt)

    if not params:
        param_container = soup.find("div", attrs={"data-testid": "ad-attributes"}) or soup.find(
            "div", class_=re.compile(r"css-.*attributes")
        )
        if param_container:
            for item in param_container.find_all(["div", "p", "span", "li"]):
                txt = item.get_text(strip=True)
                if ":" in txt and len(txt) < 80 and txt not in params:
                    params.append(txt)

    result["params_text"] = " | ".join(params)

    desc_node = (
        soup.find("div", attrs={"data-testid": "ad-description-text"})
        or soup.find("div", attrs={"data-cy": "ad_description"})
        or soup.find("div", attrs={"data-cy": "ad-description-text"})
        or soup.find("div", attrs={"data-testid": "textContainer"})
        or soup.find("section", attrs={"data-testid": "ad-description-section"})
        or soup.find("div", class_=re.compile(r"css-.*(description|textContainer)"))
    )

    if desc_node:
        for junk in desc_node.find_all(["h2", "h3", "button", "svg", "span"]):
            if "Pokaż więcej" in junk.get_text() or "Więcej" in junk.get_text():
                junk.decompose()
        for br in desc_node.find_all("br"):
            br.replace_with("\n")
        raw_desc = desc_node.get_text(separator="\n", strip=True)
        result["description"] = clean_text(raw_desc)

    date_span = (
        soup.find("span", attrs={"data-testid": "ad-posted-at"})
        or soup.find("span", attrs={"data-cy": "ad-posted-at"})
    )
    if date_span:
        result["posted_at"] = date_span.get_text(strip=True).replace("Dodane", "").strip()

    loc_span = (
        soup.find("a", href=re.compile(r"/d/oferta/.*#location"))
        or soup.find("p", class_=re.compile(r"css-.*location"))
        or soup.find("span", attrs={"data-testid": "location-date-container"})
    )
    if loc_span:
        result["location"] = loc_span.get_text(strip=True).split("-")[0].strip()

    if not result["description"] or result["price"] is None:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "{}")
                if isinstance(data, dict):
                    if not result["description"] and data.get("description"):
                        result["description"] = clean_text(data["description"])
                    if result["price"] is None and "offers" in data:
                        offers_obj = data["offers"]
                        if isinstance(offers_obj, dict) and "price" in offers_obj:
                            result["price"] = parse_price(str(offers_obj["price"]))
                    if not result["location"]:
                        addr = data.get("offers", {}).get("availableAtOrFrom", {}).get("address", {})
                        if isinstance(addr, dict) and addr.get("addressLocality"):
                            result["location"] = addr.get("addressLocality")
            except Exception:
                pass

    return result