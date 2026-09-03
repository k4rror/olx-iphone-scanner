from olx_scanner.ai.json_repair import auto_repair_json


def test_repair_think_and_markdown():
    raw_output = """
    <think>
    Thinking process...
    </think>
    ```json
    {
      "exact_model": "iPhone 13 Pro",
      "storage_gb": 128,
      "battery_health_pct": 87,
      "is_damaged": false
    }
    ```
    """
    data = auto_repair_json(raw_output)
    assert data is not None
    assert data["exact_model"] == "iPhone 13 Pro"
    assert data["battery_health_pct"] == 87
    assert data["is_damaged"] is False


def test_repair_unclosed_json():
    broken = '{"exact_model": "iPhone 12", "battery_health_pct": 82'
    data = auto_repair_json(broken)
    assert data is not None
    assert data["exact_model"] == "iPhone 12"