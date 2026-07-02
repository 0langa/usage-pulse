"""Token estimation without storing prompt bodies."""

from __future__ import annotations

import math


def estimate_tokens(text: str, model: str | None = None) -> int:
    if not text:
        return 0
    try:
        import tiktoken

        encoding = tiktoken.encoding_for_model(model or "gpt-4o")
        return len(encoding.encode(text))
    except Exception:
        return max(1, math.ceil(len(text) / 4))
