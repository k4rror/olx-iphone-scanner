import pytest
from olx_scanner.ai.heuristics import is_likely_iphone_offer


@pytest.mark.parametrize(
    ("title", "price", "expected"),
    [
        ("iPhone 13 Pro 128GB błękitny igła", 2200, True),
        ("Apple iPhone 15 256GB czarny", 3100, True),
        ("Samsung Galaxy S24 Ultra jak iPhone", 3500, False),
        ("Etui skórzane case MagSafe do iPhone 15 Pro", 80, False),
        ("Pudełko oryginalne box iPhone 14 Pro Max", 50, False),
        ("iPhone 14 Pro", 30, False),
    ],
)
def test_iphone_heuristics(title: str, price: float, expected: bool):
    is_valid, _ = is_likely_iphone_offer(title=title, price=price)
    assert is_valid == expected