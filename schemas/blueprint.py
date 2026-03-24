# Pydantic v2 response schemas for the JSON blueprint returned by the AI.

import re
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, field_validator


class ContentBlock(BaseModel):
    """A generic block of content (Hero, Footer, etc.) defined by a numeric type."""
    type: int = Field(..., description="Numeric identifier for the component type (e.g. 1 for Hero, 4 for Footer)")
    style: int = Field(1, description="Style variation for the component")
    is_hidden: bool = Field(False, description="Whether this block should be hidden")
    
    # Optional fields depending on the block type
    title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    image_url: str | None = None
    phone: str | None = None
    email: str | None = None
    location: str | None = None
    logo_url: str | None = None
    social_links: list[dict[str, str]] | None = None
    images: list[str] | None = None


class PageBlueprint(BaseModel):
    """The complete page layout returned by the AI."""
    community_id: int = Field(..., description="Community ID for the landing page")
    template: int = Field(1, description="Overall template style for the page")
    content: list[ContentBlock] = Field(
        ...,
        description="Ordered list of content blocks (e.g., Hero, Footer) to render top-to-bottom",
    )


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    raw_ai_response: str | None = None

class PatchCommand(BaseModel):
    """A granular update to an existing block instead of a full blueprint."""
    action: str = Field(description="'update_block' | 'add_block' | 'delete_block'")
    type: int = Field(description="The numeric block type to target (e.g. 1 for Hero)")
    updates: dict[str, Any] = Field(description="Key-value pairs to update (e.g. {'title': 'New Hero'})")
