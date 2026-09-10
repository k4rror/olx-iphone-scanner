from pathlib import Path

from olx_scanner.web.scanner_service import ScannerService, clean_dashboard_text


def test_clean_dashboard_text():
    # Test usuwania kodów ANSI oraz znaczników Rich
    raw_ansi = "\x1b[32m[bold green]Testowy komunikat[/bold green]\x1b[0m"
    clean = clean_dashboard_text(raw_ansi)
    assert clean == "Testowy komunikat"
    assert "\x1b" not in clean
    assert "[" not in clean


def test_scanner_service_lifecycle(tmp_path: Path):
    db_file = tmp_path / "service_test.db"
    svc = ScannerService(db_path=str(db_file))

    # Stan początkowy
    snap = svc.get_snapshot()
    assert snap["is_running"] is False
    assert snap["status_code"] == "idle"

    # Logowanie zdarzeń bez narzutu Rich
    svc.log_event("AI", "[bold cyan]Rozpoznano iPhone 13[/bold cyan]", idx="99901")
    snap_after = svc.get_snapshot()
    assert len(snap_after["recent_logs"]) == 1
    assert snap_after["recent_logs"][0]["level"] == "AI"
    assert snap_after["recent_logs"][0]["message"] == "Rozpoznano iPhone 13"
    assert snap_after["recent_logs"][0]["idx"] == "99901"