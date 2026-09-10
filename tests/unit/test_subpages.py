from fastapi.testclient import TestClient

from olx_scanner.web.app import app

client = TestClient(app)


def test_root_redirects_to_scanner():
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/scanner"


def test_subpage_scanner_renders():
    response = client.get("/scanner")
    assert response.status_code == 200
    assert "Centrum Skanera" in response.text or "centrum skanera" in response.text.lower()
    assert "Parametry" in response.text
    assert "static/js/scanner.js" in response.text


def test_subpage_offers_renders():
    response = client.get("/offers")
    assert response.status_code == 200
    assert "baza ofert" in response.text.lower() or "oferty" in response.text.lower()
    assert "static/js/offers.js" in response.text


def test_subpage_analytics_renders():
    response = client.get("/analytics")
    assert response.status_code == 200
    assert "analityka" in response.text.lower()
    assert "static/js/analytics.js" in response.text