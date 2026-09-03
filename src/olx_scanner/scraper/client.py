from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable
from bs4 import BeautifulSoup
import tls_client

from olx_scanner.core.models import VerifiedProxy
from olx_scanner.scraper.parsers import extract_full_offer_data_from_html, parse_price

TARGET_BASE_URL = "https://www.olx.pl"
TARGET_SEARCH_URL = "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/q-iphone/"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.olx.pl/",
    "Origin": "https://www.olx.pl",
    "DNT": "1",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


def create_tls_session(proxy_url: str | None = None) -> tls_client.Session:
    session = tls_client.Session(
        client_identifier="chrome_120",
        random_tls_extension_order=True,
    )
    session.headers.update(HEADERS)
    if proxy_url and proxy_url != "Direct":
        session.proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }
    return session


class TLSScraper:
    def __init__(
        self,
        verified_proxies: list[VerifiedProxy] | None = None,
        static_proxy: str | None = None,
        logger: Callable[[str, str, str | None], None] | None = None,
    ) -> None:
        self.proxies: list[VerifiedProxy] = list(verified_proxies or [])
        self.static_proxy = static_proxy
        self.log = logger or (lambda msg, lvl="SCRAPE", idx=None: None)
        self._lock = threading.Lock()
        self._rr_index = 0

    def get_proxy(self) -> str | None:
        if self.static_proxy:
            return self.static_proxy
        with self._lock:
            if not self.proxies:
                return None
            proxy = self.proxies[self._rr_index % len(self.proxies)]
            self._rr_index += 1
            return proxy.url

    def mark_proxy_failed(self, proxy_url: str, idx: str | None = None) -> None:
        with self._lock:
            for p in list(self.proxies):
                if p.url == proxy_url:
                    p.fails += 1
                    if p.fails >= 3:
                        self.proxies.remove(p)
                        self.log(f"Proxy {proxy_url} usunięte z puli. Pozostało: {len(self.proxies)}", "ERROR", idx=idx)
                    break

    def fetch_page(self, page: int = 1) -> tuple[int, list[dict[str, Any]], str | None]:
        url = (
            f"{TARGET_SEARCH_URL}?search%5Border%5D=created_at%3Adesc"
            if page == 1
            else f"{TARGET_SEARCH_URL}?page={page}&search%5Border%5D=created_at%3Adesc"
        )
        idx_tag = f"PAGE-{page}"

        for _ in range(1, 4):
            proxy = self.get_proxy()
            if not proxy:
                break
            try:
                session = create_tls_session(proxy)
                response = session.get(url, timeout_seconds=5, allow_redirects=True)
                if response.status_code == 200:
                    offers = self._parse_html_cards(response.text)
                    if offers:
                        return 200, offers, proxy
                self.mark_proxy_failed(proxy, idx=idx_tag)
            except Exception:
                self.mark_proxy_failed(proxy, idx=idx_tag)

        # Fallback Direct TLS
        try:
            session = create_tls_session(None)
            response = session.get(url, timeout_seconds=7, allow_redirects=True)
            if response.status_code == 200:
                offers = self._parse_html_cards(response.text)
                return 200, offers, "Direct"
            return response.status_code, [], "Direct"
        except Exception as exc:
            return 0, [], str(exc)

    def fetch_full_offer_details(self, offer_url: str, proxy: str | None = None, idx: str | None = None) -> dict[str, Any]:
        html_text = ""
        used_proxy = proxy if (proxy and proxy != "Direct") else self.get_proxy()

        if used_proxy:
            try:
                session = create_tls_session(used_proxy)
                resp = session.get(offer_url, timeout_seconds=5, allow_redirects=True)
                if resp.status_code == 200 and ("ad-description" in resp.text or "opis" in resp.text.lower()):
                    html_text = resp.text
                else:
                    self.mark_proxy_failed(used_proxy, idx=idx)
            except Exception:
                self.mark_proxy_failed(used_proxy, idx=idx)

        if not html_text:
            try:
                session = create_tls_session(None)
                resp = session.get(offer_url, timeout_seconds=6, allow_redirects=True)
                if resp.status_code == 200:
                    html_text = resp.text
            except Exception:
                pass

        return extract_full_offer_data_from_html(html_text, logger=self.log, idx=idx)

    def _parse_html_cards(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        cards = soup.find_all("div", attrs={"data-cy": "l-card"})
        for card in cards:
            try:
                olx_id = card.get("id")
                title_link = card.find("a", attrs={"data-testid": "card-title-link"}) or card.find("a", href=re.compile(r"/d/oferta/"))
                if not title_link:
                    continue
                title = title_link.get_text(strip=True)
                href = title_link.get("href", "")
                full_url = f"{TARGET_BASE_URL}{href}" if href.startswith("/") else href
                clean_url = full_url.split("?")[0]
                if not olx_id:
                    m = re.search(r"-ID([a-zA-Z0-9]+)\.html", clean_url)
                    olx_id = m.group(1) if m else clean_url

                price_elem = card.find("span", attrs={"data-testid": "ad-price"}) or card.find("p", attrs={"data-testid": "ad-price"})
                price_val = parse_price(price_elem.get_text(strip=True)) if price_elem else None

                loc_s, date_s = "", ""
                loc_date_elem = card.find("p", attrs={"data-testid": "location-date"})
                if loc_date_elem:
                    text = loc_date_elem.get_text(strip=True)
                    if " - " in text:
                        loc_s, _, date_s = text.partition(" - ")
                    else:
                        loc_s = text
                else:
                    p5_tags = card.find_all("p", attrs={"data-nx-name": "P5"})
                    loc_s = p5_tags[0].get_text(strip=True) if len(p5_tags) > 0 else ""
                    date_s = p5_tags[1].get_text(strip=True) if len(p5_tags) > 1 else ""

                offers.append({
                    "olx_id": str(olx_id),
                    "url": clean_url,
                    "title": title,
                    "price": price_val,
                    "currency": "PLN",
                    "location": loc_s.strip(),
                    "posted_at": date_s.strip(),
                    "description": "",
                })
            except Exception:
                continue
        return offers