from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from typing import Any

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
