# Google Gemini wrapper (google-genai SDK), used by the article summarizer.
# Reads GOOGLE_API_KEY from environment. Raises RuntimeError if the key is missing.
#
# NOTE: services/gemini.py is a misleadingly-named legacy *Grok* wrapper and is
# dead code. This module is the real Gemini client for shared use; routes/
# categorize.py still holds its own client for its category-specific schema.

import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# gemini-3.5-flash-lite: measured the best Dutch of the candidates (natural word
# order and inversion, no calqued English structure) at ~1.3s, and it shares the
# top free-tier quota bucket with 3.1-flash-lite (15 RPM / 500 RPD). The non-lite
# Flash models (3/3.5/3.6/3.7) are capped at 20 requests/day, far too low for a
# summarizer that pays once per article per language. Override with GEMINI_SUMMARY_MODEL.
SUMMARY_MODEL = os.getenv("GEMINI_SUMMARY_MODEL", "gemini-3.5-flash-lite")

# gemini-3.5-flash-lite REJECTS thinking_budget=0 with a bare 400 INVALID_ARGUMENT
# (it is thinking-mandatory); thinking_level="low" is the portable equivalent and
# 3.1-flash-lite accepts it too. "low" also measured faster and cleaner than the
# model default here, so don't raise it without re-checking both.
_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "low")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY is not set. Add it to your .env file.")
        _client = genai.Client(api_key=key)
    return _client


def generate_json(prompt: str, system: str | None = None, max_tokens: int = 800,
                  model: str | None = None, response_schema: dict | None = None,
                  temperature: float = 0.3) -> str:
    """Send a prompt to Gemini and return raw JSON text.

    Thinking is pinned low — the summarizer is latency-bound and gains nothing from
    long reasoning. Thought tokens can still be emitted, and response.text may
    concatenate them, so we extract the non-thought part explicitly.
    """
    client = _get_client()
    config_kwargs: dict = {
        "response_mime_type": "application/json",
        "thinking_config": types.ThinkingConfig(thinking_level=_THINKING_LEVEL),
        "max_output_tokens": max_tokens,
        "temperature": temperature,
    }
    if system:
        config_kwargs["system_instruction"] = system
    if response_schema:
        config_kwargs["response_schema"] = response_schema

    response = client.models.generate_content(
        model=model or SUMMARY_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    try:
        parts = response.candidates[0].content.parts or []
        text = next((p.text for p in parts if p.text and not getattr(p, "thought", False)), None)
    except (AttributeError, IndexError, TypeError):
        text = None
    text = text or (response.text or "")
    if not text.strip():
        raise ValueError("Gemini returned empty response")
    return text


def check_api_status() -> dict:
    """Returns {"reachable": bool, "reason": str | None} for health probes."""
    if not os.getenv("GOOGLE_API_KEY"):
        return {"reachable": False, "reason": "GOOGLE_API_KEY is not set"}
    try:
        raw = generate_json('Return this exact JSON: {"status": "connected"}', max_tokens=50)
        ok = "connected" in raw
        return {"reachable": ok, "reason": None if ok else "Gemini returned unexpected output"}
    except Exception as e:
        logger.error("Gemini check_api_status failed: %s", e)
        return {"reachable": False, "reason": f"Gemini API unreachable: {e}"}
