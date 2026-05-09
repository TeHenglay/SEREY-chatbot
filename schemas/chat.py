# Pydantic v2 request/response schemas for the chatbot API.

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime, timezone
from schemas.blueprint import PageBlueprint, PatchCommand


class ChatLink(BaseModel):
    """A navigable link the AI recommends — rendered as a button on the frontend."""
    label: str = Field(..., description="Display text for the button")
    url: str = Field(..., description="Full URL to navigate to")
    type: str = Field(default="page", description="'shop' | 'product' | 'page' | 'community'")
    community_id: int | None = Field(default=None, description="Community ID for type='community' links")
    image: str | None = Field(default=None, description="Avatar/icon URL for the community")


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        description="The user's chat message",
        min_length=1,
        max_length=4000,
        examples=["Can you make the hero section use a blue gradient?"],
    )
    user_id: str = Field(
        ...,
        description="Unique identifier for the user (for long-term memory)",
        min_length=1,
        max_length=128,
        examples=["user_123"],
    )
    session_id: str = Field(
        ...,
        description="Unique identifier for the current chat session",
        min_length=1,
        max_length=128,
        examples=["session_abc"],
    )
    community_id: int | None = Field(
        default=None,
        description="Community ID to embed in generated blueprints. Required for builder chat.",
    )
    page_context: str | None = Field(
        default=None,
        description="Current page state snapshot sent by the frontend on every turn.",
        max_length=16000,
    )
    flow: str | None = Field(
        default=None,
        description="Named flow to activate: 'post_guide' | 'community_discovery'",
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="The AI assistant's reply")
    links: list[ChatLink] = Field(default_factory=list, description="Actionable links extracted from the reply")
    user_id: str = Field(..., description="Echoed user_id for reference")
    session_id: str = Field(..., description="Echoed session_id for reference")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UploadNeeded(BaseModel):
    section: str = Field(..., description="Section type, e.g. 'gallery', 'hero'")
    field: str = Field(..., description="Field name, e.g. 'images', 'image_url'")
    index: Optional[int] = Field(default=None, description="Array index for list fields")
    label: str = Field(..., description="Human-readable upload prompt label")


class StyleSelection(BaseModel):
    section: str = Field(..., description="Section type in lowercase")
    style: int = Field(..., description="Resolved style ID for this section")
    is_hidden: bool = Field(default=False, description="Whether the section is hidden")
    style_reason: Optional[str] = Field(
        default=None,
        description="Optional AI rationale for the chosen style",
    )


class BuilderChatResponse(BaseModel):
    """Response from the builder chatbot. Always has a reply; blueprint is present when
    the AI generates or updates a page layout."""
    reply: str = Field(..., description="Conversational reply from the AI")
    uploads_needed: Optional[list[UploadNeeded]] = Field(
        default=None,
        description="Upload prompts the frontend should render when sections need images",
    )
    styles_selected: Optional[list[StyleSelection]] = Field(
        default=None,
        description="Final resolved style per section after backend validation",
    )
    blueprint: Optional[PageBlueprint] = Field(
        default=None,
        description="Generated page blueprint if the user asked to build/modify a page",
    )
    patches: Optional[list[PatchCommand]] = Field(
        default=None,
        description="List of granular updates to apply to the existing blueprint without rewriting it entirely.",
    )
    user_id: str = Field(..., description="Echoed user_id for reference")
    session_id: str = Field(..., description="Echoed session_id for reference")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
