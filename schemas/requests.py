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
