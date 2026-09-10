from pathlib import Path

from olx_scanner.storage.database import Database


def test_dashboard_filtering_and_pagination(tmp_path: Path):
    db_path = tmp_path / "test_dash.db"
    db = Database(db_path)

    # 1. Zasilenie danymi testowymi
    offers = [
        {
            "olx_id": "1001",
            "url": "https://olx.pl/d/1001",
            "title": "iPhone 13 Pro 128GB",
            "price": 2200.0,
            "description": "Idealny stan, bateria 88%",
        },
        {
            "olx_id": "1002",
            "url": "https://olx.pl/d/1002",
            "title": "iPhone 14 256GB Niebieski",
            "price": 2800.0,
            "description": "Nowy z salonu, kondycja 100%",
        },
        {
            "olx_id": "1003",
            "url": "https://olx.pl/d/1003",
            "title": "iPhone 11 uszkodzony ekran",
            "price": 600.0,
            "description": "Zbita szybka, bateria 75%",
        },
    ]

    for o in offers:
        db.insert_raw_offer(o)

    # Aktualizacja analizy AI
    db.update_ai_analysis("1001", {
        "exact_model": "iPhone 13 Pro",
        "storage_gb": 128,
        "battery_health_pct": 88,
        "is_damaged": False,
        "face_id_working": True,
        "icloud_clean": True,
        "condition": "Bardzo dobry",
        "ai_verdict": "Bardzo opłacalna oferta",
    })
    db.update_ai_analysis("1002", {
        "exact_model": "iPhone 14",
        "storage_gb": 256,
        "battery_health_pct": 100,
        "is_damaged": False,
        "face_id_working": True,
        "icloud_clean": True,
        "condition": "Jak nowy",
        "ai_verdict": "Stan sklepowy",
    })
    db.update_ai_analysis("1003", {
        "exact_model": "iPhone 11",
        "storage_gb": 64,
        "battery_health_pct": 75,
        "is_damaged": True,
        "face_id_working": False,
        "icloud_clean": True,
        "condition": "Uszkodzony",
        "ai_verdict": "Wymaga wymiany ekranu",
    })

    # 2. Test filtrowania po cenie i modelu
    res = db.query_offers(min_price=2000.0, max_price=2500.0)
    assert res["total"] == 1
    assert res["items"][0]["olx_id"] == "1001"

    # 3. Test filtrowania po uszkodzeniach
    damaged_res = db.query_offers(is_damaged=True)
    assert damaged_res["total"] == 1
    assert damaged_res["items"][0]["exact_model"] if "exact_model" in damaged_res["items"][0] else damaged_res["items"][0]["model_name"] == "iPhone 11"

    # 4. Test przełączania ulubionych
    assert db.toggle_favorite("1001") is True
    assert db.get_offer_by_id("1001")["is_favorite"] == 1
    assert db.toggle_favorite("1001") is False
    assert db.get_offer_by_id("1001")["is_favorite"] == 0

    # 5. Test notatek użytkownika
    assert db.update_notes("1002", "Zadzwonić we wtorek") is True
    assert db.get_offer_by_id("1002")["user_notes"] == "Zadzwonić we wtorek"

    # 6. Test usuwania
    assert db.delete_offer("1003") is True
    assert db.offer_exists("1003") is False

    # 7. Test agregatów analitycznych
    analytics = db.get_analytics_summary()
    assert len(analytics["models_price"]) >= 1
    assert analytics["battery_distribution"]["bat_85_89"] == 1
    assert analytics["battery_distribution"]["bat_90_100"] == 1

def test_model_aggregate_stats(tmp_path: Path):
    db_path = tmp_path / "test_model_stats.db"
    db = Database(db_path)

    # 1. Dodanie 2 ofert tego samego modelu o różnych cenach i baterii
    db.insert_raw_offer({
        "olx_id": "2001",
        "url": "https://olx.pl/d/2001",
        "title": "iPhone 13 Pro 128GB",
        "price": 2000.0,
        "description": "bateria 90%",
    })
    db.insert_raw_offer({
        "olx_id": "2002",
        "url": "https://olx.pl/d/2002",
        "title": "iPhone 13 Pro 256GB",
        "price": 2400.0,
        "description": "bateria 80%",
    })

    db.update_ai_analysis("2001", {
        "exact_model": "iPhone 13 Pro",
        "storage_gb": 128,
        "battery_health_pct": 90,
        "is_damaged": False,
    })
    db.update_ai_analysis("2002", {
        "exact_model": "iPhone 13 Pro",
        "storage_gb": 256,
        "battery_health_pct": 80,
        "is_damaged": False,
    })

    # 2. Weryfikacja obliczeń agregujących
    stats = db.get_model_stats("iPhone 13 Pro")
    assert stats is not None
    assert stats["total_count"] == 2
    assert stats["avg_price"] == 2200.0   # (2000 + 2400) / 2
    assert stats["min_price"] == 2000.0
    assert stats["max_price"] == 2400.0
    assert stats["avg_battery"] == 85.0   # (90 + 80) / 2
    assert stats["healthy_count"] == 2
    assert stats["damaged_count"] == 0
    
def test_margin_filtering_and_sorting(tmp_path: Path):
    db_path = tmp_path / "test_margin.db"
    db = Database(db_path)

    # Trzy oferty tego samego modelu o różnych cenach
    offers = [
        {"olx_id": "3001", "url": "https://olx.pl/d/3001", "title": "iPhone 13 Pro OKAZJA", "price": 1600.0},
        {"olx_id": "3002", "url": "https://olx.pl/d/3002", "title": "iPhone 13 Pro Średnia", "price": 2000.0},
        {"olx_id": "3003", "url": "https://olx.pl/d/3003", "title": "iPhone 13 Pro Drogi", "price": 2400.0},
    ]
    for o in offers:
        db.insert_raw_offer(o)
        db.update_ai_analysis(o["olx_id"], {
            "exact_model": "iPhone 13 Pro",
            "is_damaged": False,
        })

    # Średnia modelu to (1600 + 2000 + 2400) / 3 = 2000 zł
    # Marża dla 3001: 2000 - 1600 = +400 zł (+20%)
    # Marża dla 3002: 2000 - 2000 = 0 zł
    # Marża dla 3003: 2000 - 2400 = -400 zł (-20%)

    # 1. Test sortowania od największej marży
    res_sorted = db.query_offers(sort_by="margin_desc")
    assert res_sorted["items"][0]["olx_id"] == "3001"
    assert res_sorted["items"][0]["margin_pln"] == 400.0
    assert res_sorted["items"][0]["margin_pct"] == 20.0
    assert res_sorted["items"][2]["olx_id"] == "3003"
    assert res_sorted["items"][2]["margin_pln"] == -400.0

    # 2. Test filtru "Tylko okazje" (marża > 0)
    res_deals = db.query_offers(only_deals=True)
    assert res_deals["total"] == 1
    assert res_deals["items"][0]["olx_id"] == "3001"

    # 3. Test filtru minimalnej kwoty marży (np. >= 300 zł)
    res_min_margin = db.query_offers(min_margin=300.0)
    assert res_min_margin["total"] == 1
    assert res_min_margin["items"][0]["olx_id"] == "3001"

    # 4. Weryfikacja pobierania pojedynczej oferty wraz z marżą
    off_details = db.get_offer_by_id("3001")
    assert off_details is not None
    assert off_details["avg_model_price"] == 2000.0
    assert off_details["margin_pln"] == 400.0