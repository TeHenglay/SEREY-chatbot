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


def generate_text(prompt: str) -> str:
    """Send a prompt to Grok and return a plain text response (for chatbot use)."""
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
                logger.warning("Grok text attempt 1 failed (%s), retrying in 2s...", str(e))
                time.sleep(2)
            else:
                raise


async def stream_text(prompt: str):
    """
    Async generator that yields raw text chunks from Grok's streaming API.

    The async client streams chunks; they are yielded as they arrive.
    Retries once after a 2-second (non-blocking) wait on failure.
    """
    client = _get_async_client()

    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=_GROK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                stream=True,
            )
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return
        except Exception as e:
            if attempt == 0:
                logger.warning("Grok stream attempt 1 failed (%s), retrying in 2s...", str(e))
                await asyncio.sleep(2)
            else:
                raise


def test_connection() -> bool:
    """Returns True if Grok is reachable, False otherwise."""
    try:
        if not os.getenv("GROK_API_KEY"):
            return False
        result = generate('Return this exact JSON: {"status": "connected"}')
        return "connected" in result
    except Exception as e:
        logger.error("Grok test_connection failed: %s", str(e))
        return False
