# AI service — wraps xAI Grok 3 via the OpenAI-compatible API.
# Reads XAI_API_KEY from environment. Raises RuntimeError if key is missing.
#
# Models:
#   grok-3          — most capable, best for full blueprint generation
#   grok-3-fast     — faster, good for patch/chat replies
#   grok-3-mini     — cheapest, for simple conversational turns

import asyncio
import os
import time
import logging
from openai import OpenAI, APIError, APITimeoutError

logger = logging.getLogger(__name__)

XAI_BASE_URL = "https://api.x.ai/v1"
MODEL_BLUEPRINT = "grok-3"       # full page generation — best quality
MODEL_CHAT      = "grok-3-fast"  # conversational replies — faster


def _get_client() -> OpenAI:
    key = os.getenv("XAI_API_KEY")
    if not key:
        raise RuntimeError("XAI_API_KEY is not set. Add it to your .env file.")
    return OpenAI(api_key=key, base_url=XAI_BASE_URL)


def _call_with_retry(fn, *args, retries: int = 2, delay: float = 2.0, **kwargs):
    last_exc = None
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except (APITimeoutError, APIError) as e:
            last_exc = e
            if attempt < retries - 1:
                logger.warning("Grok attempt %d failed (%s), retrying in %.1fs...", attempt + 1, str(e), delay)
                time.sleep(delay)
    raise last_exc


def generate(
    prompt: str,
    system_prompt: str | None = None,
    use_thinking: bool = False,
    temperature: float = 0.4,
) -> str:
    """Send a prompt to Grok 3 and return the raw JSON string response.

    Args:
        prompt: The user message / full prompt.
        system_prompt: Optional system instruction injected as a system message.
        use_thinking: If True, uses grok-3 (full model) with reasoning_effort=high
                      for complex full-page blueprint generation.
        temperature: Sampling temperature (0.3-0.5 for JSON, 0.7 for text).
    """
    client = _get_client()
    model = MODEL_BLUEPRINT if use_thinking else MODEL_BLUEPRINT

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    # Enable extended reasoning for full blueprint generation
    if use_thinking:
        kwargs["reasoning_effort"] = "high"

    def _call():
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

    result = _call_with_retry(_call)
    if not result:
        raise ValueError("Grok returned empty response")
    return result


def generate_text(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
) -> str:
    """Send a prompt to Grok and return a plain text response (for chat replies)."""
    client = _get_client()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    def _call():
        resp = client.chat.completions.create(
            model=MODEL_CHAT,
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content

    result = _call_with_retry(_call)
    if not result:
        raise ValueError("Grok returned empty response")
    return result


def generate_with_history(
    messages: list[dict],
    system_prompt: str | None = None,
    json_mode: bool = False,
    use_thinking: bool = False,
    temperature: float = 0.5,
) -> str:
    """Generate a reply given a full conversation history (list of role/content dicts).

    Args:
        messages: List of {"role": "user"|"assistant", "content": str} dicts.
        system_prompt: Injected as the first system message if provided.
        json_mode: If True, forces JSON output format.
        use_thinking: If True, uses reasoning_effort=high.
        temperature: Sampling temperature.
    """
    client = _get_client()
    model = MODEL_BLUEPRINT if (json_mode or use_thinking) else MODEL_CHAT

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    kwargs = dict(
        model=model,
        messages=full_messages,
        temperature=temperature,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if use_thinking:
        kwargs["reasoning_effort"] = "high"

    def _call():
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

    result = _call_with_retry(_call)
    if not result:
        raise ValueError("Grok returned empty response")
    return result


async def stream_text(prompt: str, system_prompt: str | None = None):
    """Async generator that yields text chunks from Grok's streaming API."""
    client = _get_client()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(2):
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        _SENTINEL = object()

        def _blocking_stream():
            try:
                stream = client.chat.completions.create(
                    model=MODEL_CHAT,
                    messages=messages,
                    temperature=0.7,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        loop.call_soon_threadsafe(queue.put_nowait, delta)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

        fut = loop.run_in_executor(None, _blocking_stream)
        try:
            while True:
                item = await asyncio.wait_for(queue.get(), timeout=60.0)
                if item is _SENTINEL:
                    await fut
                    return
                if isinstance(item, Exception):
                    raise item
                yield item
            return
        except asyncio.TimeoutError:
            logger.error("Grok stream_text timed out after 60s")
            raise
        except Exception as e:
            if attempt == 0:
                logger.warning("Grok stream attempt 1 failed (%s), retrying in 2s...", str(e))
                await asyncio.sleep(2)
            else:
                raise


def test_connection() -> bool:
    """Returns True if Grok is reachable, False otherwise."""
    try:
        if not os.getenv("XAI_API_KEY"):
            return False
        result = generate('{"status": "connected"}', temperature=0.1)
        return "connected" in result
    except Exception as e:
        logger.error("Grok test_connection failed: %s", str(e))
        return False
