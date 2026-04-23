# Wraps the Google Gemini API for generating JSON blueprints and plain-text chat.
# Reads GOOGLE_API_KEY from environment. Raises RuntimeError if key is missing.

import asyncio
import google.generativeai as genai
import os
import time
import logging

logger = logging.getLogger(__name__)

_api_key = os.getenv("GOOGLE_API_KEY")
if _api_key:
    genai.configure(api_key=_api_key)

# Module-level cached model instances — built once, reused for every request.
_json_model: genai.GenerativeModel | None = None
_text_model: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    global _json_model
    if _json_model is None:
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY is not set. Add it to your .env file.")
        genai.configure(api_key=key)
        _json_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={"response_mime_type": "application/json"},
        )
    return _json_model


def _get_text_model() -> genai.GenerativeModel:
    global _text_model
    if _text_model is None:
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY is not set. Add it to your .env file.")
        genai.configure(api_key=key)
        _text_model = genai.GenerativeModel(model_name="gemini-2.5-flash")
    return _text_model


def generate(prompt: str) -> str:
    """Send a prompt to Gemini and return the raw JSON string response."""
    model = _get_model()
    for attempt in range(2):
        try:
            response = model.generate_content(prompt)
            if not response.text:
                raise ValueError("Gemini returned empty response")
            return response.text
        except Exception as e:
            if attempt == 0:
                logger.warning("Gemini attempt 1 failed (%s), retrying in 2s...", str(e))
                time.sleep(2)
            else:
                raise


def generate_text(prompt: str) -> str:
    """Send a prompt to Gemini and return a plain text response (for chatbot use)."""
    model = _get_text_model()
    for attempt in range(2):
        try:
            response = model.generate_content(prompt)
            if not response.text:
                raise ValueError("Gemini returned empty response")
            return response.text
        except Exception as e:
            if attempt == 0:
                logger.warning("Gemini text attempt 1 failed (%s), retrying in 2s...", str(e))
                time.sleep(2)
            else:
                raise


async def stream_text(prompt: str):
    """
    Async generator that yields raw text chunks from Gemini's streaming API.

    The blocking SDK iterator runs in a thread-pool executor; chunks are pushed
    into an asyncio.Queue so the event loop is never blocked between tokens.
    Retries once after a 2-second (non-blocking) wait on failure.
    """
    model = _get_text_model()

    for attempt in range(2):
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        _SENTINEL = object()

        def _blocking_stream():
            try:
                response_iter = model.generate_content(prompt, stream=True)
                for chunk in response_iter:
                    if chunk.text:
                        loop.call_soon_threadsafe(queue.put_nowait, chunk.text)
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
            logger.error("Gemini stream_text timed out after 60s")
            raise
        except Exception as e:
            if attempt == 0:
                logger.warning("Gemini stream attempt 1 failed (%s), retrying in 2s...", str(e))
                await asyncio.sleep(2)
            else:
                raise


def test_connection() -> bool:
    """Returns True if Gemini is reachable, False otherwise."""
    try:
        if not os.getenv("GOOGLE_API_KEY"):
            return False
        result = generate('Return this exact JSON: {"status": "connected"}')
        return "connected" in result
    except Exception as e:
        logger.error("Gemini test_connection failed: %s", str(e))
        return False
