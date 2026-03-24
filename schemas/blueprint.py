# Pydantic v2 schemas for the Serey V2 landing page builder.
# Section types use string identifiers matching the frontend V2 component registry.
# API contract: POST /api/v2/landing-pages body = { community_id, content: [...sections] }

from typing import Any, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-item models
# ---------------------------------------------------------------------------

class GalleryImage(BaseModel):
    image_url: str = ""
    name: str = ""
    description: str = ""


class SocialLink(BaseModel):
    type: str = Field(..., description="facebook | instagram | telegram | twitter")
    handle: str = ""
    url: str | None = None


class VideoItem(BaseModel):
    url: str
    title: str = ""
    thumbnail: str = ""


class TeamMember(BaseModel):
    name: str
    role: str = ""
    image_url: str = ""


class FAQItem(BaseModel):
    q: str
    a: str


class TestimonialItem(BaseModel):
    name: str = ""
    role: str = ""
    quote: str
    image_url: str = ""


# ---------------------------------------------------------------------------
# Section block — one unified model with all optional section-specific fields.
# `type` must be one of the 12 V2 section type strings.
# ---------------------------------------------------------------------------

SECTION_TYPES = Literal[
    "HERO", "ABOUT", "GALLERY", "FOOTER",
    "VIDEO", "VISION", "BLOG", "TEAM",
    "FAQ", "TESTIMONIALS", "CUSTOM", "RANKING",
]


class SectionBlock(BaseModel):
    """A single section in the V2 landing page content array."""

    type: SECTION_TYPES = Field(..., description="Section type string, e.g. 'HERO'")
    style: int = Field(1, description="Style variant number (see MD for options per type)")
    is_hidden: bool = Field(False)
    colors: dict[str, str] | None = Field(
        None,
        description="Color overrides: title, accent, body, bg, subtitle, goal_color, vision_color, mission_color",
    )

    # --- shared text fields ---
    title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    image_url: str | None = None

    # --- GALLERY ---
    images: list[GalleryImage] | None = None

    # --- FOOTER ---
    phone: str | None = None
    email: str | None = None
    location: str | None = None
    logo_url: str | None = None
    social_links: list[SocialLink] | None = None

    # --- VIDEO ---
    videos: list[VideoItem] | None = None

    # --- VISION ---
    goals_title: str | None = None
    goals_description: str | None = None
    vision_title: str | None = None
    vision_description: str | None = None
    mission_title: str | None = None
    mission_description: str | None = None

    # --- TEAM ---
    members: list[TeamMember] | None = None

    # --- FAQ ---
    faq_items: list[FAQItem] | None = None

    # --- TESTIMONIALS ---
    testimonial_items: list[TestimonialItem] | None = None

    # --- CUSTOM ---
    button_label: str | None = None
    button_url: str | None = None
    image_url_2: str | None = None


# ---------------------------------------------------------------------------
# Page blueprint — matches the POST /api/v2/landing-pages body exactly.
# ---------------------------------------------------------------------------

class PageBlueprint(BaseModel):
    """The complete landing page layout.
    Frontend saves this via: POST /api/v2/landing-pages { community_id, content }"""

    community_id: int = Field(..., description="Community ID for the landing page")
    content: list[SectionBlock] = Field(
        ...,
        description="Ordered list of section blocks rendered top-to-bottom",
    )


# ---------------------------------------------------------------------------
# Patch command — granular update to a single section without full rewrite.
# ---------------------------------------------------------------------------

class PatchCommand(BaseModel):
    """A targeted update to an existing section in the page layout."""

    action: str = Field(
        ...,
        description="'update_block' | 'add_block' | 'delete_block'",
    )
    type: str = Field(
        ...,
        description="Section type string to target, e.g. 'HERO'",
    )
    updates: dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value pairs to apply (e.g. {'title': 'New Title'})",
    )


# ---------------------------------------------------------------------------
# Error response
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    raw_ai_response: str | None = None
