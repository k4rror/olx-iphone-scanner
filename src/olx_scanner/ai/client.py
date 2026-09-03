from __future__ import annotations

import os
import time
from typing import Any, Callable
from openai import OpenAI

from olx_scanner.ai.json_repair import auto_repair_json
from olx_scanner.ai.prompts import SYSTEM_PROMPTS
from olx_scanner.core.models import IPhoneAnalysis

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash-vision-exp"


class DeepSeekAnalyzer:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEEPSEEK_BASE_URL,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        language: str = "en",
        logger: Callable[[str, str, str | None], None] | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url
        self.model = (model or DEFAULT_DEEPSEEK_MODEL).strip().lower()
        self.language = language if language in SYSTEM_PROMPTS else "en"
        self.log = logger or (lambda msg, lvl="AI", idx=None: None)
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key or "missing-key", timeout=30.0)

    def set_language(self, language: str) -> None:
        if language in SYSTEM_PROMPTS:
            self.language = language

    def analyze_listing(
        self,
        title: str,
        price: float | None,
        params_text: str,
        description: str,
        idx: str | int | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        if not self.api_key:
            self.log("Brak klucza DEEPSEEK_API_KEY!", "ERROR", idx=idx)
            return None, "Brak klucza API"

        system_prompt = SYSTEM_PROMPTS.get(self.language, SYSTEM_PROMPTS["en"])
        user_message = (
            f"Title: {title}\n"
            f"Price: {f'{price:.0f} PLN' if price is not None else 'N/A'}\n"
            f"Attributes: {params_text or 'None'}\n\n"
            f"Description:\n{description if description else 'No description'}\n"
        )

        self.log(
            f"DeepSeek ({self.model}) [Lang: {self.language.upper()}] | {len(user_message)} chars...",
            "AI",
            idx=idx,
        )

        for attempt in range(1, 3):
            t0 = time.perf_counter()
            try:
                completion_params = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 3000,
                    "response_format": {"type": "json_object"},
                    "timeout": 25.0,
                }

                try:
                    completion = self.client.chat.completions.create(
                        **completion_params,
                        extra_body={"thinking": {"type": "disabled"}},
                    )
                except Exception as ex_think:
                    if "thinking" in str(ex_think).lower() or "400" in str(ex_think):
                        completion = self.client.chat.completions.create(**completion_params)
                    else:
                        raise ex_think

                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                content = completion.choices[0].message.content

                if content:
                    raw_dict = auto_repair_json(content)
                    if raw_dict:
                        try:
                            validated = IPhoneAnalysis.model_validate(raw_dict)
                            parsed = validated.model_dump()
                        except Exception:
                            parsed = raw_dict

                        tokens = getattr(completion, "usage", None)
                        tokens_s = f" ({tokens.total_tokens} tokenów)" if tokens else ""
                        self.log(
                            f"JSON OK ({elapsed_ms}ms{tokens_s}): {parsed.get('exact_model')} | Bateria: {parsed.get('battery_health_pct')}% | Stan: {parsed.get('condition')}",
                            "AI",
                            idx=idx,
                        )
                        return parsed, content
                    else:
                        self.log(f"Błąd dekodowania JSON ({elapsed_ms}ms)", "WARN", idx=idx)
                        return None, content
                else:
                    self.log(f"Pusta odpowiedź z API w próbie {attempt}", "WARN", idx=idx)

            except Exception as e:
                err_str = str(e)
                self.log(f"Błąd DeepSeek API (próba {attempt}): {err_str}", "WARN", idx=idx)
                if "429" in err_str:
                    time.sleep(2.0)
                    continue
                time.sleep(0.5)

        return None, "Błąd komunikacji z DeepSeek API po 2 próbach"