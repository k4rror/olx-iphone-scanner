# tests/unit/test_database.py
from pathlib import Path

from olx_scanner.storage.database import Database


def test_database_insert_and_deduplication(tmp_path: Path):
    db_path = tmp_path / "test_iphones.db"
    db = Database(db_path)

    offer = {
        "olx_id": "999001",
        "url": "https://www.olx.pl/d/oferta/iphone-13-ID999001.html",
        "title": "iPhone 13 128GB BDB",
        "price": 1850.0,
        "currency": "PLN",
        "location": "Warszawa",
        "posted_at": "Dzisiaj 14:00",
        "description": "Bateria 88%.",
    }

    assert db.insert_raw_offer(offer) is True
    assert db.offer_exists("999001") is True
    assert db.insert_raw_offer(offer) is False  # Odrzucenie duplikatu


def test_database_page_scan_records(tmp_path: Path):
    db_path = tmp_path / "test_pages.db"
    db = Database(db_path)

    db.record_page_scan(
        page_number=1,
        offers_total=30,
        new_offers=5,
        fingerprint="fingerprint_hash_123",
        duration_s=1.25,
    )

    assert db.get_last_page_fingerprint(1) == "fingerprint_hash_123"
    assert db.get_stats()["pages_scanned"] == 1
