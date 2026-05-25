# Pydantic v2 schemas for the Serey V2 landing page builder.
# Section types use numeric IDs (1-12) in API responses; strings are used internally.
# API contract: POST /api/v2/landing-pages body = { template, font, animation_style, community_id, content: [...sections] }

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, field_serializer


# Numeric type ID → canonical string name
SECTION_TYPE_ID_MAP: dict[int, str] = {
    1: "HERO",
    2: "ABOUT",
    3: "GALLERY",
    4: "FOOTER",
    5: "VIDEO",
    6: "VISION",
    7: "BLOG",
    8: "TEAM",
    9: "FAQ",
    10: "TESTIMONIALS",
    11: "CUSTOM",
    12: "RANKING",
}

_SECTION_TYPE_NAME_TO_ID: dict[str, int] = {v: k for k, v in SECTION_TYPE_ID_MAP.items()}


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


def _normalize_social_links(v: list) -> list:
    result = []
    for item in v:
        if isinstance(item, str):
            url = item.lower()
            handle = item.rstrip("/").split("/")[-1]
            link_type = "other"
            for platform in ["facebook", "instagram", "telegram", "twitter", "youtube", "tiktok"]:
                if platform in url:
                    link_type = platform
                    break
            result.append({"type": link_type, "handle": handle, "url": item})
        else:
            result.append(item)
    return result


class VideoItem(BaseModel):
    url: str
    title: str = ""
    thumbnail: str = ""


class TeamMember(BaseModel):
    name: str
    role: str = ""
    image_url: str = ""


class FAQItem(BaseModel):
    question: str
    answer: str

    @field_validator("question", mode="before")
    @classmethod
    def _compat_q(cls, v: Any, info: Any) -> Any:
        return v

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> "FAQItem":
        if isinstance(obj, dict):
            # Accept legacy q/a keys
            if "q" in obj and "question" not in obj:
                obj = {**obj, "question": obj["q"]}
            if "a" in obj and "answer" not in obj:
                obj = {**obj, "answer": obj["a"]}
        return super().model_validate(obj, **kwargs)


class TestimonialItem(BaseModel):
    name: str = ""
    role: str = ""
    content: str  # was "quote" in earlier versions
    image_url: str = ""

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> "TestimonialItem":
        if isinstance(obj, dict) and "quote" in obj and "content" not in obj:
            obj = {**obj, "content": obj["quote"]}
        return super().model_validate(obj, **kwargs)


# ---------------------------------------------------------------------------
# Section block — one unified model with all optional section-specific fields.
# `type` is stored as a string internally and serialized as an int for the frontend.
# ---------------------------------------------------------------------------

SECTION_TYPES = Literal[
    "HERO", "ABOUT", "GALLERY", "FOOTER",
    "VIDEO", "VISION", "BLOG", "TEAM",
    "FAQ", "TESTIMONIALS", "CUSTOM", "RANKING",
]


class SectionBlock(BaseModel):
    """A single section in the V2 landing page content array."""

    type: SECTION_TYPES = Field(..., description="Section type string, e.g. 'HERO' (stored as string, serialized as int)")
    style: int = Field(1, description="Style variant number (see layout_policy for options per type)")
    is_hidden: bool = Field(False)
    instance_key: str | None = Field(None, description="Unique key for duplicate section instances, e.g. 'team_1'")
    colors: dict[str, str] | None = Field(
        None,
        description="Color overrides: title, accent, body, bg, subtitle, goal_color, vision_color, mission_color",
    )
    text_styles: dict[str, Any] | None = Field(None, description="Optional per-section text style overrides")
    bg_image_url: str = Field("", description="Background image URL — leave empty; user-uploaded")
    bg_image_opacity: float = Field(0.5, description="Background image opacity 0.0–1.0")

    # --- shared text fields ---
    title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    image_url: str | None = None
    image_ratio: str | None = None
    image_width: int | None = None
    image_height: int | None = None

    # --- GALLERY ---
    images: list[GalleryImage] | None = None

    # --- FOOTER ---
    phone: str | None = None
    email: str | None = None
    location: str | None = None
    logo_url: str | None = None
    social_links: list[SocialLink] | None = None

    @field_validator("social_links", mode="before")
    @classmethod
    def normalize_social_links(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return v
        return _normalize_social_links(v)

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
    image_url_3: str | None = None

    # --- RANKING ---
    authors: list[Any] | None = None

    @field_serializer("type")
    def serialize_type(self, value: str) -> int:
        """Output numeric type ID for the frontend."""
        return _SECTION_TYPE_NAME_TO_ID.get(value, 0)


# ---------------------------------------------------------------------------
# Page blueprint — matches the POST /api/v2/landing-pages body exactly.
# ---------------------------------------------------------------------------

class PageBlueprint(BaseModel):
    """The complete landing page layout."""

    template: int = Field(1, description="Template ID — always 1")
    font: str = Field("", description="Google Font name or empty string")
    animation_style: str = Field(
        "fade",
        description="Scroll entrance animation: none | fade | slide-up | slide-left | blur",
    )
    community_id: int = Field(..., description="Community ID for the landing page")
    content: list[SectionBlock] = Field(
        ...,
        description="Ordered list of section blocks rendered top-to-bottom (Hero first, Footer last)",
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
    instance_key: str | None = Field(None, description="Target a specific instance, e.g. 'team_2'")
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
