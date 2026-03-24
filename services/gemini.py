# Wraps the Google Gemini API for generating JSON blueprints.
# Reads GOOGLE_API_KEY from environment. Raises RuntimeError if key is missing.

import google.generativeai as genai
import os
import time
import logging

logger = logging.getLogger(__name__)

_api_key = os.getenv("GOOGLE_API_KEY")
if _api_key:
    genai.configure(api_key=_api_key)

def _get_model():
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not set. Add it to your .env file.")
    genai.configure(api_key=key)
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )


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
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not set. Add it to your .env file.")
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name="gemini-2.5-flash")
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
