# Wraps the xAI Grok API for generating JSON blueprints and plain-text chat.
# Reads GROK_API_KEY from environment. Raises RuntimeError if key is missing.
# Grok supports multiple languages including Khmer.

import asyncio
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
import os
import time
import logging

logger = logging.getLogger(__name__)

_api_key = os.getenv("GROK_API_KEY")

# xAI Grok API endpoint (OpenAI-compatible)
_GROK_BASE_URL = "https://api.x.ai/v1"
_GROK_MODEL = "grok-3-mini"
_GROK_BUILDER_MODEL = "grok-4.3"
# Vision model for image-understanding calls. Override with GROK_VISION_MODEL
# (e.g. "grok-2-vision-1212") if the default rejects image input.
_GROK_VISION_MODEL = os.getenv("GROK_VISION_MODEL", "grok-4.3")
# Article TL;DR summaries. Kept separate from _GROK_MODEL so the summarizer can
# move without dragging /api/chat and /chat/stream along.
# NOTE: "grok-3-mini" above is a retired alias — xAI silently routes it to
# grok-4.3, so CHAT_MODEL does not reflect what actually serves those requests.
# grok-4.3 measured at ~4s for a 3-bullet Dutch summary; grok-4.6 took ~161s on
# the same input (it reasons first) and blew the 40s timeout below, turning the
# first reader's request into a 502. Dutch quality was equivalent. Don't "upgrade"
# to 4.5/4.6 here without re-measuring latency against that timeout.
_GROK_SUMMARY_MODEL = os.getenv("GROK_SUMMARY_MODEL", "grok-4.3")

# Public aliases for route-level logging
CHAT_MODEL = _GROK_MODEL
BUILDER_MODEL = _GROK_BUILDER_MODEL
VISION_MODEL = _GROK_VISION_MODEL
SUMMARY_MODEL = _GROK_SUMMARY_MODEL

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


BUILDER_CALL_TIMEOUT_S = 90.0


def empty_usage() -> dict:
    return {"prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0}


def add_usage(total: dict, extra: dict) -> dict:
    """Sum token counts — every billed attempt must reach serey-api's meter."""
    return {k: total.get(k, 0) + extra.get(k, 0) for k in empty_usage()}


class UnusableBuilderOutput(Exception):
    """The model answered (and billed tokens) but the output cannot be used:
    empty, or cut off at max_tokens. Carries the counts so they are not lost."""

    def __init__(self, reason: str, text: str, counts: dict):
        super().__init__(reason)
        self.reason = reason
        self.text = text
        self.counts = counts


# Fast, transient failures worth one immediate retry. Timeouts are NOT here: a
# second slow attempt cannot fit in serey-api's 120s proxy budget.
_TRANSIENT_ERRORS = (APIConnectionError, RateLimitError, InternalServerError)


def _usage_counts(response) -> dict:
    usage = response.usage
    if not usage:
        return empty_usage()
    cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
    logger.info("Builder usage: prompt=%d cached=%d completion=%d", usage.prompt_tokens, cached, usage.completion_tokens)
    return {
        "prompt_tokens": usage.prompt_tokens or 0,
        "cached_tokens": cached,
        "completion_tokens": usage.completion_tokens or 0,
    }


def generate_builder_with_usage(
    prompt: str, system: str | None = None, timeout: float = BUILDER_CALL_TIMEOUT_S
) -> tuple[str, dict]:
    """Send a prompt to Grok using the builder model.

    Returns the raw JSON text AND what the call cost in tokens (serey-api bills
    AI credits per turn from these). Raises UnusableBuilderOutput when the model
    answered but the text is empty or truncated, so the caller can decide
    whether a re-generation fits its time budget.

    SDK-level retries are disabled (the default 2 retries also retry timeouts,
    tripling worst-case latency); this function retries once, on fast transient
    errors only, within the given timeout.
    """
    client = _get_client().with_options(max_retries=0)
    messages = _build_messages(prompt, system)
    deadline = time.monotonic() + timeout
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=_GROK_BUILDER_MODEL,
                messages=messages,
                temperature=0.7,
                # 4096 could truncate a large 7-section blueprint mid-JSON,
                # guaranteeing a parse failure + retry + 422.
                max_tokens=8192,
                timeout=max(deadline - time.monotonic(), 1.0),
                extra_headers={"x-grok-conv-id": "serey-builder-v1"},
            )
        except _TRANSIENT_ERRORS as e:
            # APITimeoutError subclasses APIConnectionError — never retry it.
            if attempt == 0 and not isinstance(e, APITimeoutError) and deadline - time.monotonic() > 30:
                logger.warning("Grok builder transient error (%s), retrying in 2s...", str(e))
                time.sleep(2)
                continue
            raise
        counts = _usage_counts(response)
        choice = response.choices[0]
        text = choice.message.content or ""
        if choice.finish_reason == "length":
            raise UnusableBuilderOutput("truncated at max_tokens", text, counts)
        if not text.strip():
            raise UnusableBuilderOutput("empty response", text, counts)
        return text, counts
    raise RuntimeError("unreachable")


def generate_builder(prompt: str, system: str | None = None) -> str:
    """Text-only wrapper, for callers that do not meter (routes/builder.py)."""
    text, _usage = generate_builder_with_usage(prompt, system)
    return text


def generate_vision(text_prompt: str, image_urls: list[str], system: str | None = None) -> str:
    """Send a text prompt plus images to the Grok vision model, return raw text.

    Images are passed by URL (must be publicly fetchable). Low temperature —
    used for deterministic tasks like matching product names to photos.
    """
    client = _get_client()
    content: list[dict] = [{"type": "text", "text": text_prompt}]
    content += [
        {"type": "image_url", "image_url": {"url": url, "detail": "low"}}
        for url in image_urls
    ]
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=_GROK_VISION_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=1500,
                timeout=60,
            )
            if not response.choices[0].message.content:
                raise ValueError("Grok returned empty vision response")
            return response.choices[0].message.content
        except Exception as e:
            if attempt == 0:
                logger.warning("Grok vision attempt 1 failed (%s), retrying in 2s...", str(e))
                time.sleep(2)
            else:
                raise


def generate_text(prompt: str, system: str | None = None, max_tokens: int = 1500,
                  model: str | None = None) -> str:
    """Send a prompt to Grok and return a plain text response (for chatbot use).

    `model` overrides the default chat model for callers that need a different
    one (e.g. the article summarizer); leave it None for chat/stream behaviour.
    """
    client = _get_client()
    messages = _build_messages(prompt, system)
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model or _GROK_MODEL,
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
