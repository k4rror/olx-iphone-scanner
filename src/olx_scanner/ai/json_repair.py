from __future__ import annotations

import json
import re
from typing import Any


def auto_repair_json(broken_text: str) -> dict[str, Any] | None:
    if not broken_text:
        return None

    clean = re.sub(r"<think>[\s\S]*?</think>", "", broken_text)
    clean = re.sub(r"```(?:json)?", "", clean).strip("` \n\r\t")

    try:
        return json.loads(clean)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*", clean)
    if not match:
        return None

    text = match.group(0).strip()
    num_quotes = len(re.findall(r'(?<!\\)"', text))
    if num_quotes % 2 != 0:
        text += '"'

    text = re.sub(r',\s*"[^"]*":?\s*$', "", text)
    open_b = text.count("{")
    close_b = text.count("}")
    if open_b > close_b:
        text += "}" * (open_b - close_b)

    try:
        return json.loads(text)
    except Exception:
        return None
