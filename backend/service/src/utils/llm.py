from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"


def generate_patch(code: str, api_key: str | None = None) -> str:
    """Call an LLM API to generate a patch based on the code."""
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not provided")

    headers = {"Authorization": f"Bearer {api_key}"}
    payload: dict[str, Any] = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "Generate a patch for the given code"},
            {"role": "user", "content": code},
        ],
    }

    logger.info("calling LLM")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(OPENAI_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            patch = data["choices"][0]["message"]["content"]
            logger.debug("received patch")
            return patch
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM call failed", exc=exc)
        return f"LLM call failed: {exc}"
