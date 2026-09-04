import pytest


@pytest.fixture
def sample_html_offer():
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <div data-testid="ad-price-container">
            <p data-nx-name="P1">2 150 zł</p>
        </div>
        <span data-nx-name="P3">Stan: Używane</span>
        <span data-nx-name="P3">Wbudowana pamięć: 128 GB</span>
        <div data-testid="ad-description-text">
            Telefon w stanie idealnym.<br>Kondycja baterii 89%.
        </div>
        <span data-testid="ad-posted-at">Dodane Dzisiaj o 12:45</span>
    </body>
    </html>
    """
