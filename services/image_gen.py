# AI image generation for the landing-page builder (xAI Grok Imagine).
#
# Used for the first-build auto fill: when a user finishes onboarding without
# uploading any images, the hero and about photos are generated so the page
# keeps the template's image layouts instead of falling back to text-only ones.
#
# Returns the image model's TEMPORARY URL. Storing it permanently is the
# Next.js builder proxy's job — it holds the storage credentials, this service
# never does.

import logging
import os

from services.grok import _get_client

logger = logging.getLogger(__name__)

# grok-imagine-image followed business-specific briefs best in a side-by-side
# test (2026-10-08) at ~$0.02/image; -quality is ~2.5x the price.
IMAGE_MODEL = os.getenv("GROK_IMAGE_MODEL", "grok-imagine-image")
IMAGE_TIMEOUT_S = 45.0

# Appended to every prompt: the builder must never produce text in images,
# brand marks, or identifiable people (fake staff/customers would mislead).
_SAFETY_SUFFIX = (
    " Natural photographic style, soft natural light. No text, letters, numbers, logos or "
    "watermarks anywhere in the image. No identifiable faces — show hands, objects, places "
    "and atmosphere instead."
)


def generate_image(prompt: str, aspect_ratio: str = "16:9", timeout: float = IMAGE_TIMEOUT_S) -> str:
    """Generate one image and return its temporary URL. Raises on failure."""
    client = _get_client().with_options(max_retries=0, timeout=timeout)
    response = client.images.generate(
        model=IMAGE_MODEL,
        prompt=(prompt.strip() + _SAFETY_SUFFIX)[:4000],
        n=1,
        response_format="url",
        extra_body={"aspect_ratio": aspect_ratio},
    )
    url = response.data[0].url if response.data else None
    if not url:
        raise ValueError("Image model returned no URL")
    return url
