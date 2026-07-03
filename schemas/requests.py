# Pydantic v2 request schemas for the builder API.

from pydantic import BaseModel, Field, model_validator
from typing import Any


class BuilderChatRequest(BaseModel):
    """
    Schema for POST /api/builder/chat.
    Accepts both 'message' (frontend) and 'prompt' (legacy) field names.
    """
    # Frontend sends 'message'; legacy clients may send 'prompt'
    message: str | None = Field(None, min_length=1, max_length=8000)
    prompt: str | None = Field(None, min_length=1, max_length=8000)

    user_id: str = Field(..., min_length=1, max_length=128)
    session_id: str = Field(..., min_length=1, max_length=128)
    community_id: str | int | None = Field(None)

    # Full page context string sent by the frontend (describes current page state)
    page_context: str | None = Field(None, max_length=20000)

    # How many ChromaDB component results to fetch (frontend doesn't send this)
    n_components: int = Field(default=4, ge=1, le=8)

    @model_validator(mode="after")
    def resolve_message(self) -> "BuilderChatRequest":
        """Normalize: prefer 'message', fall back to 'prompt'. One must be present."""
        if not self.message and not self.prompt:
            raise ValueError("Either 'message' or 'prompt' must be provided.")
        if not self.message:
            self.message = self.prompt
        return self


class BuilderRequest(BaseModel):
    """Legacy schema — kept for backwards compatibility."""
    prompt: str = Field(..., min_length=3, max_length=2000)
    user_id: str = Field(..., min_length=1, max_length=128)
    session_id: str = Field(..., min_length=1, max_length=128)
    n_components: int = Field(default=4, ge=1, le=8)


# ---------------------------------------------------------------------------
# POST /api/builder/match-products — vision matching of product names to
# uploaded product photos.
# ---------------------------------------------------------------------------

class ImageSlot(BaseModel):
    """One uploaded product photo. `index` is the frontend's slot position,
    echoed back untouched so the caller can apply matches in place."""
    image_url: str = Field(..., min_length=8, max_length=2000)
    index: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def check_url(self) -> "ImageSlot":
        if not self.image_url.startswith(("http://", "https://")):
            raise ValueError("image_url must be an http(s) URL")
        return self


class ProductInfo(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    details: str = Field("", max_length=500)


class MatchProductsRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    session_id: str = Field(..., min_length=1, max_length=128)
    community_id: str | int | None = Field(None)
    images: list[ImageSlot] = Field(..., min_length=1, max_length=12)
    products: list[ProductInfo] = Field(..., min_length=1, max_length=12)
    language: str | None = Field(None, description="Description language, e.g. 'en' | 'kh'")


class ProductMatch(BaseModel):
    image_url: str
    index: int | None = None
    name: str = ""          # matched product name; "" when no confident match
    description: str = ""   # short grounded description; "" when unmatched
    confidence: str = "low"  # high | medium | low


class MatchProductsResponse(BaseModel):
    matches: list[ProductMatch]
    unmatched_products: list[str]
    reply: str
