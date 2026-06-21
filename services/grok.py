# Wraps the xAI Grok API for generating JSON blueprints and plain-text chat.
# Reads GROK_API_KEY from environment. Raises RuntimeError if key is missing.
# Grok supports multiple languages including Khmer.

import asyncio
from openai import OpenAI, AsyncOpenAI
import os
import time
import logging

logger = logging.getLogger(__name__)

_api_key = os.getenv("GROK_API_KEY")

# xAI Grok API endpoint (OpenAI-compatible)
_GROK_BASE_URL = "https://api.x.ai/v1"
_GROK_MODEL = "grok-3-mini"
_GROK_BUILDER_MODEL = "grok-4.3"

# Public aliases for route-level logging
CHAT_MODEL = _GROK_MODEL
BUILDER_MODEL = _GROK_BUILDER_MODEL

# Module-level cached client instances
_client: OpenAI | None = None
_async_client: AsyncOpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.getenv("GROK_API_KEY")
        if not key:
            raise RuntimeError("GROK_API_KEY is not set. Add it to your .env file.")
        _client = OpenAI(api_key=key, base_url=_GROK_BASE_URL)
    return _client


def _get_async_client() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        key = os.getenv("GROK_API_KEY")
        if not key:
            raise RuntimeError("GROK_API_KEY is not set. Add it to your .env file.")
        _async_client = AsyncOpenAI(api_key=key, base_url=_GROK_BASE_URL)
    return _async_client


def _build_messages(prompt: str, system: str | None) -> list[dict]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


def generate(prompt: str) -> str:
    """Send a prompt to Grok and return the raw JSON string response."""
    client = _get_client()
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=_GROK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            if not response.choices[0].message.content:
                raise ValueError("Grok returned empty response")
            return response.choices[0].message.content
        except Exception as e:
            if attempt == 0:
                logger.warning("Grok attempt 1 failed (%s), retrying in 2s...", str(e))
                time.sleep(2)
            else:
                raise


def generate_builder(prompt: str, system: str | None = None) -> str:
    """Send a prompt to Grok using the builder model and return raw JSON text."""
    client = _get_client()
    messages = _build_messages(prompt, system)
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=_GROK_BUILDER_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=4096,
                timeout=60,
                extra_headers={"x-grok-conv-id": "serey-builder-v1"},
            )
            if not response.choices[0].message.content:
                raise ValueError("Grok returned empty response")
            usage = response.usage
            if usage:
                cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
                logger.info("Builder usage: prompt=%d cached=%d completion=%d", usage.prompt_tokens, cached, usage.completion_tokens)
            return response.choices[0].message.content
        except Exception as e:
            if attempt == 0:
                logger.warning("Grok builder attempt 1 failed (%s), retrying in 2s...", str(e))
                time.sleep(2)
            else:
                raise


def generate_text(prompt: str, system: str | None = None, max_tokens: int = 1500) -> str:
    """Send a prompt to Grok and return a plain text response (for chatbot use)."""
    client = _get_client()
    messages = _build_messages(prompt, system)
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=_GROK_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=max_tokens,
                timeout=40,
            )
            if not response.choices[0].message.content:
                raise ValueError("Grok returned empty response")
            return response.choices[0].message.content
        except Exception as e:
            if attempt == 0:
                logger.warning("Grok text attempt 1 failed (%s), retrying in 2s...", str(e))
                time.sleep(2)
            else:
                raise


async def stream_text(prompt: str, system: str | None = None):
    """
    Async generator that yields raw text chunks from Grok's streaming API.

    The async client streams chunks; they are yielded as they arrive.
    Retries once after a 2-second (non-blocking) wait on failure.
    """
    client = _get_async_client()
    messages = _build_messages(prompt, system)

    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=_GROK_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
                stream=True,
                timeout=40,
            )
            async for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
            return
        except Exception as e:
            if attempt == 0:
                logger.warning("Grok stream attempt 1 failed (%s), retrying in 2s...", str(e))
                await asyncio.sleep(2)
            else:
                raise


def check_api_status() -> dict:
    """
    Returns {"reachable": bool, "quota_ok": bool, "reason": str | None}.
    Distinguishes quota exhaustion (429 rate-limit, or 403 credits/spending-limit)
    from other failures so callers can surface the difference — and a human-readable
    reason — in health/monitoring endpoints.
    """
    from openai import RateLimitError

    if not os.getenv("GROK_API_KEY"):
        return {"reachable": False, "quota_ok": True, "reason": "GROK_API_KEY is not set"}
    try:
        result = generate('Return this exact JSON: {"status": "connected"}')
        ok = "connected" in result
        reason = None if ok else "Grok responded but health probe returned unexpected output"
        return {"reachable": ok, "quota_ok": True, "reason": reason}
    except RateLimitError as e:
        msg = str(e)
        logger.error("Grok quota/rate-limit exceeded: %s", msg)
        return {"reachable": True, "quota_ok": False, "reason": f"Grok rate-limit/quota exceeded: {msg}"}
    except Exception as e:
        msg = str(e)
        logger.error("Grok check_api_status failed: %s", msg)
        # xAI returns 403 permission-denied (not 429) when a team has used all
        # available credits or hit its monthly spending limit. Treat that as a
        # quota problem so monitors can act on billing rather than connectivity.
        lowered = msg.lower()
        if "credit" in lowered or "spending limit" in lowered or "permission-denied" in lowered or "permission_denied" in lowered:
            return {
                "reachable": True,
                "quota_ok": False,
                "reason": f"Grok billing/quota error (add credits or raise spending limit in the xAI console): {msg}",
            }
        return {"reachable": False, "quota_ok": True, "reason": f"Grok API unreachable: {msg}"}


def test_connection() -> bool:
    """Returns True if Grok is reachable and quota is available."""
    status = check_api_status()
    return status["reachable"] and status["quota_ok"]
