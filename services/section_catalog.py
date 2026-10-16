# Single source of truth for everything the AI builder must know about the
# Serey V2 landing-page frontend.
#
# Section styles, colour keys and animation styles are LOADED from
# services/builder_ai/builder-section-catalog.json — an exact copy of
# fe-serey-web docs/ai/builder-section-catalog.json, which the frontend
# generates from LandingBuilderV2.js (scripts/export-ai-builder-prompt.js).
# Never edit that copy by hand: regenerate it in the frontend and copy it over;
# eval/catalog_check.py fails while the copy differs from the frontend file.
# The rest of this module mirrors frontend constants by hand (noted per block).

from __future__ import annotations

import json
import os
from typing import Any

BUILDER_AI_DIR = os.path.join(os.path.dirname(__file__), "builder_ai")
CATALOG_JSON_PATH = os.path.join(BUILDER_AI_DIR, "builder-section-catalog.json")
PROMPT_MD_PATH = os.path.join(BUILDER_AI_DIR, "builder-ai-prompt.md")

with open(CATALOG_JSON_PATH, encoding="utf8") as _f:
    FE_CATALOG: dict[str, Any] = json.load(_f)

# Section name ("HERO") -> its catalog entry
FE_SECTIONS: dict[str, dict[str, Any]] = {s["name"]: s for s in FE_CATALOG["sections"]}

# Custom HTML blocks (top-level `code_blocks` response key): actions with their
# required/optional fields, html length cap, height/width ranges.
CODE_BLOCKS_SPEC: dict[str, Any] = FE_CATALOG.get("code_blocks") or {}

_SYSTEM_PROMPT_HEADING = "## SYSTEM PROMPT"


def builder_prompt_from_doc() -> str:
    """The builder system prompt from builder-ai-prompt.md: everything from the
    "## SYSTEM PROMPT" heading to the end. The header above it is notes for humans."""
    with open(PROMPT_MD_PATH, encoding="utf8") as f:
        text = f.read().replace("\r\n", "\n")
    lines = text.split("\n")
    start = next(i for i, line in enumerate(lines) if line.strip() == _SYSTEM_PROMPT_HEADING)
    return "\n".join(lines[start:]).strip()

# ---------------------------------------------------------------------------
# Section types
# Mirrors: fe-serey-web src/config/constants.js LANDING_PAGE_TEMPLATE_TYPE_V2
# and LandingBuilderV2.js resolveTypeKey(); _validate() checks it against the
# catalog JSON.
# NOTE: NEWSLETTER (14) exists in the frontend enum but resolveTypeKey has no
# numeric mapping for it — the AI must use SUBSCRIPTION (13) instead.
# TEXTBLOCK is string-only: it has no numeric ID and must be emitted as the
# string "TEXTBLOCK" (the frontend string map accepts it).
# ---------------------------------------------------------------------------

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
    13: "SUBSCRIPTION",
    14: "NEWSLETTER",
    15: "NOTES",
    16: "PODCAST",
}

SECTION_TYPE_NAME_TO_ID: dict[str, int] = {v: k for k, v in SECTION_TYPE_ID_MAP.items()}

# String-only section types (no numeric ID; serialized as the string itself)
STRING_ONLY_SECTION_TYPES: tuple[str, ...] = ("TEXTBLOCK",)

ALL_SECTION_TYPES: tuple[str, ...] = tuple(SECTION_TYPE_ID_MAP.values()) + STRING_ONLY_SECTION_TYPES

# ---------------------------------------------------------------------------
# Layout styles per section — value, label, description — from the catalog
# JSON. Every listed style is valid for the AI, whatever its `status`:
# "picker" (has a chip), "variant" (e.g. ABOUT 10/11/12) or "hidden" (HERO 2).
# Order matches the catalog; the FIRST value is the fallback for an invalid style.
# GALLERY with section_subtype "product" has its own list (PRODUCT_STYLES).
# ---------------------------------------------------------------------------


def _style_rows(styles: list[dict[str, Any]]) -> tuple[tuple[int, str, str], ...]:
    return tuple((int(s["value"]), s["label"], s.get("description", "")) for s in styles)


SECTION_STYLES: dict[str, tuple[tuple[int, str, str], ...]] = {
    name: _style_rows(section["styles"]) for name, section in FE_SECTIONS.items()
}
# Not in the catalog: sections the AI may not send (CUSTOM, NEWSLETTER) or
# that have a single layout (TEXTBLOCK). Kept so existing pages still resolve.
SECTION_STYLES.update({
    "CUSTOM": ((1, "Code", "The user's own HTML & CSS in a sandboxed iframe"),),
    "NEWSLETTER": ((1, "Default", "Simple newsletter signup block"),),
    "TEXTBLOCK": ((1, "Default", "Free-form rich text block"),),
})

PRODUCT_STYLES: tuple[tuple[int, str, str], ...] = _style_rows(FE_SECTIONS["GALLERY"]["product_styles"])
PRODUCT_SUBTYPE_STYLES: tuple[int, ...] = tuple(v for v, _label, _desc in PRODUCT_STYLES)


def allowed_styles(section_type: str) -> tuple[int, ...]:
    return tuple(v for v, _label, _desc in SECTION_STYLES.get(section_type, ((1, "", ""),)))


def style_label(section_type: str, style: int) -> str:
    for value, label, _desc in SECTION_STYLES.get(section_type, ()):
        if value == style:
            return label
    return f"Style {style}"


# ---------------------------------------------------------------------------
# Image fields rendered per section/style — drives uploads_needed derivation.
# Mirrors: LandingBuilderV2.js IMAGE_FIELD_STYLE_RULES + isImageFieldRenderable().
# Scalar image fields are only requested for styles that actually render them;
# array item images (gallery/team/testimonials) render on every style except
# TESTIMONIALS style 7 ("Cards No Image").
# ---------------------------------------------------------------------------

def _build_rendered_fields() -> dict[str, dict[int, tuple[str, ...]]]:
    rendered: dict[str, dict[int, tuple[str, ...]]] = {}
    scalar_rules: dict[str, dict[str, tuple[int, ...]]] = {
        # Verified against the renderers (Shared/LandingPageV2/HeroSection.js,
        # AboutSection.js): hero style 3 (Centered) and about styles 1 (Panel),
        # 4 (Text Only) and 9 (Split Panel) render no image; about 13
        # (Spotlight) renders a main photo plus a small accent photo.
        # Hero 2 (Cinematic) and the about variants 10/11/12 come from the
        # catalog JSON: 10 (Social: Multi Image) shows image_url + image_url_2,
        # 11/12 (Split Panel + image) show image_url.
        "HERO": {"image_url": (1, 2, 4, 5, 6)},
        "ABOUT": {"image_url": (8, 10, 11, 12, 13), "image_url_2": (10, 13)},
    }
    array_fields: dict[str, str] = {
        "GALLERY": "images",
        "TEAM": "members",
        "TESTIMONIALS": "testimonial_items",
    }
    for section, styles in SECTION_STYLES.items():
        per_style: dict[int, tuple[str, ...]] = {}
        for value, _label, _desc in styles:
            fields: list[str] = []
            for field, style_list in scalar_rules.get(section, {}).items():
                if value in style_list:
                    fields.append(field)
            if section in array_fields:
                if not (section == "TESTIMONIALS" and value == 7):
                    fields.append(array_fields[section])
            if section == "FOOTER":
                fields.append("logo_url")
            per_style[value] = tuple(fields)
        rendered[section] = per_style
    return rendered


# Same shape layout_policy historically used: {SECTION: {"allowed_styles", "rendered_fields"}}
SECTION_STYLE_MAP: dict[str, dict[str, Any]] = {
    section: {
        "allowed_styles": allowed_styles(section),
        "rendered_fields": per_style,
    }
    for section, per_style in _build_rendered_fields().items()
}

# ---------------------------------------------------------------------------
# Upload slot labels
# ---------------------------------------------------------------------------

SCALAR_UPLOAD_LABELS: dict[tuple[str, str], str] = {
    ("hero", "image_url"): "Hero Background",
    ("about", "image_url"): "About Section Image",
    ("about", "image_url_2"): "About Accent Photo",
    ("footer", "logo_url"): "Footer Logo",
}

ARRAY_UPLOAD_LABELS: dict[tuple[str, str], str] = {
    ("gallery", "images"): "Product {n} — Image",
    ("team", "members"): "Team Member {n} Photo",
    ("testimonials", "testimonial_items"): "Reviewer {n} Avatar",
}

# ---------------------------------------------------------------------------
# Fonts — mirrors LandingBuilderV2.js FONT_OPTIONS (60 Google Fonts).
# "" (empty string) = default system font. Used for the top-level blueprint
# "font" field and the per-section text_styles *_font keys.
# ---------------------------------------------------------------------------

FONT_OPTIONS: tuple[str, ...] = (
    "Barlow", "Barlow Condensed", "Battambang", "Bebas Neue", "Bitter",
    "Bodoni Moda", "Cabin", "Caveat", "Cormorant Garamond", "Crimson Text",
    "Dancing Script", "DM Sans", "DM Serif Display", "EB Garamond", "Exo 2",
    "Figtree", "Fira Code", "Great Vibes", "Hanuman", "Inter",
    "JetBrains Mono", "Josefin Sans", "Jost", "Kantumruy Pro", "Karla",
    "Lato", "Lexend", "Libre Baskerville", "Lora", "Manrope",
    "Merriweather", "Montserrat", "Mulish", "Noto Sans Khmer", "Noto Serif Khmer",
    "Nunito", "Nunito Sans", "Open Sans", "Oswald", "Outfit",
    "Pacifico", "Playfair Display", "Plus Jakarta Sans", "Poppins", "PT Sans",
    "PT Serif", "Quicksand", "Raleway", "Roboto", "Rubik",
    "Sacramento", "Satisfy", "Siemreap", "Source Code Pro", "Source Sans 3",
    "Space Grotesk", "Space Mono", "Spectral", "Syne", "Ubuntu",
    "Urbanist", "Work Sans",
)

# ---------------------------------------------------------------------------
# Curated palettes — mirrors the palette table in LandingBuilderV2.js
# buildAiIntakePrompt(). Exact hex values; do not invent new colors.
# ---------------------------------------------------------------------------

CURATED_PALETTES: dict[str, dict[str, str]] = {
    "navy-professional": {"hero_bg": "#0f2044", "title": "#eef4ff", "accent": "#3b82f6", "section_bg": "#ffffff", "bg_alt": "#eff6ff", "vibe": "authority, corporate, SaaS"},
    "ocean-teal":        {"hero_bg": "#0c4a6e", "title": "#f0f9ff", "accent": "#0ea5e9", "section_bg": "#f0f9ff", "bg_alt": "#e0f2fe", "vibe": "health, tech, travel"},
    "forest-green":      {"hero_bg": "#052e16", "title": "#f0fdf4", "accent": "#16a34a", "section_bg": "#f0fdf4", "bg_alt": "#dcfce7", "vibe": "eco, agriculture, wellness"},
    "royal-purple":      {"hero_bg": "#1e1b4b", "title": "#f5f3ff", "accent": "#7c3aed", "section_bg": "#fafafa", "bg_alt": "#f5f3ff", "vibe": "creative, premium, luxury"},
    "warm-amber":        {"hero_bg": "#1c1917", "title": "#fef3c7", "accent": "#f59e0b", "section_bg": "#ffffff", "bg_alt": "#fffbeb", "vibe": "restaurant, food, artisan"},
    "coral-energy":      {"hero_bg": "#fff1f2", "title": "#0f172a", "accent": "#e11d48", "section_bg": "#ffffff", "bg_alt": "#fff1f2", "vibe": "fitness, events, media"},
    "editorial-cream":   {"hero_bg": "#faf6ef", "title": "#1c1a17", "accent": "#b5232a", "section_bg": "#fdf9f4", "bg_alt": "#f3ebe0", "vibe": "magazine, editorial, publishing, journalism, food & culture, literary"},
    "minimal-slate":     {"hero_bg": "#f8fafc", "title": "#0f172a", "accent": "#1d4ed8", "section_bg": "#ffffff", "bg_alt": "#f1f5f9", "vibe": "clean, portfolio, NGO"},
    "gaming-dark":       {"hero_bg": "#0d0d1a", "title": "#f0f4ff", "accent": "#7c3aed", "section_bg": "#f8f8ff", "bg_alt": "#f0f0ff", "vibe": "gaming, esports, entertainment"},
}

# ---------------------------------------------------------------------------
# Animations, image shapes, section themes
# ---------------------------------------------------------------------------

# Top-level animation_style values, from the catalog JSON (ANIM_OPTIONS).
ANIMATION_STYLES: tuple[str, ...] = tuple(FE_CATALOG["animation_styles"])

# Mirrors Shared/LandingPageV2/imageShapes.js IMAGE_SHAPE_OPTIONS
# (per-section image_shape field; "" = default/square).
IMAGE_SHAPES: tuple[str, ...] = (
    "square", "rounded", "circle", "arch", "diamond", "hexagon", "blob", "star",
)

# Per-section theme variants the renderers understand ("" = default).
SECTION_THEMES: tuple[str, ...] = ("", "editorial")

# ---------------------------------------------------------------------------
# Colors — per-section color keys, from the catalog JSON (SECTION_COLOR_CONFIG).
# All keys are hex strings inside the section "colors" object.
# ---------------------------------------------------------------------------

SECTION_COLOR_KEYS: dict[str, tuple[str, ...]] = {
    name: tuple(section["colors"]) for name, section in FE_SECTIONS.items()
}
# Not in the catalog (sections the AI may not send / single-layout).
SECTION_COLOR_KEYS.update({
    "CUSTOM": ("bg",),
    "NEWSLETTER": ("title", "bg", "accent"),
    "TEXTBLOCK": ("title", "body", "bg"),
})

# ---------------------------------------------------------------------------
# text_styles — per-section typography overrides.
# For each text slot the frontend understands suffix keys:
#   {slot}_bold (bool), {slot}_italic (bool), {slot}_font (Google Font name),
#   {slot}_size (px int), {slot}_color (hex), {slot}_align ("left"|"center"|"right")
# Universal slots: title, subtitle, description.
# Extra slots: testimonials → testi_quote / testi_name / testi_role;
#              gallery/product items → gallery_item_name / gallery_item_desc.
# Fonts set on the HERO section's text_styles are propagated to every other
# section by the frontend (propagateFontsFromHero).
# ---------------------------------------------------------------------------

TEXT_STYLE_SLOTS: tuple[str, ...] = ("title", "subtitle", "description")
TEXT_STYLE_SUFFIXES: tuple[str, ...] = ("_bold", "_italic", "_font", "_size", "_color", "_align")

# ---------------------------------------------------------------------------
# Per-section content field documentation — used to generate the system
# prompt's section registry. Mirrors LandingBuilderV2.js serializeSection().
# ---------------------------------------------------------------------------

SECTION_FIELD_DOCS: dict[str, str] = {
    "HERO": 'title, subtitle, description, image_url, image_ratio ("16:9"), image_width (null), image_height (null), image_shape ("" | square | rounded | circle | arch | diamond | hexagon | blob | star)',
    "ABOUT": 'title, subtitle, description, image_url, image_url_2 (style 13 accent photo only), image_ratio ("16:9"), image_width (null), image_height (null), image_shape',
    "GALLERY": 'title, description, images[{image_url, name, description}], section_subtype ("product" = product/services/features cards with name+description; "gallery" = plain photo grid; "project" = portfolio project cards). Every image item MUST have image_url (""), name, and description.',
    "FOOTER": 'title, description, phone, email, location, logo_url, contact_heading, social_heading, privacy_url, terms_url, social_links[{"type":"facebook"|"instagram"|"telegram","handle":"..."}]',
    "VIDEO": "title, description, videos[{url, title, thumbnail}]",
    "VISION": "title, description, goals_title, goals_description, vision_title, vision_description, mission_title, mission_description, image_url",
    "BLOG": 'title, subtitle, description, feed_type ("trending" | "latest") — posts are auto-fetched, never invent them',
    "TEAM": "title, description, members[{name, role, image_url}]",
    "FAQ": "title, faq_items[{question, answer}]",
    "TESTIMONIALS": "title, testimonial_items[{name, role, content, image_url}] (generate at most 4)",
    "CUSTOM": "html (the user's own HTML & CSS, max 50,000 chars), title (internal label, not shown) — written by the user in the code editor, never by the AI",
    "RANKING": "title, description, authors (always leave as []) — top authors are auto-fetched",
    "NOTES": 'title, description, feed_type ("trending" | "latest") — community notes are auto-fetched, never invent them',
    "PODCAST": 'title, description, feed_type ("latest" | "oldest") — episodes are auto-fetched, never invent them',
    "SUBSCRIPTION": 'title, description, button_label ("Subscribe"), placeholder_text, newsletter_provider ("" | "kit" | "email_octopus"), kit_embed_script, email_octopus_embed_script — leave provider/embed fields "" unless the user provides them',
    "TEXTBLOCK": "title, description, content (free-form rich text) — emit type as the string \"TEXTBLOCK\" (it has no numeric ID)",
}

# Gallery subtypes the frontend renders (GALLERY_SUBTYPE_LABELS / ProductSection).
GALLERY_SUBTYPES: tuple[str, ...] = ("gallery", "product", "project")

# ---------------------------------------------------------------------------
# Frontend starter templates — mirrors LandingBuilderV2/landingTemplates.js
# (LANDING_TEMPLATES). When a user builds from a template, the AI must keep
# this exact section order/structure and only rewrite content within it.
# Each section tuple: (TYPE, style, section_subtype or None, is_hidden)
# ---------------------------------------------------------------------------

FRONTEND_TEMPLATES: dict[str, dict[str, Any]] = {
    "ecommerce": {
        "label": "Online Shop",
        "animation": "slide-up",
        "font": "Mulish",
        "sections": (
            ("HERO", 1, None, False), ("ABOUT", 8, None, False),
            ("GALLERY", 1, "product", False), ("TESTIMONIALS", 7, None, False),
            ("FAQ", 1, None, False), ("FOOTER", 4, None, False),
        ),
    },
    "creator": {
        "label": "Content Creator",
        "animation": "blur",
        "font": "Inter",
        "sections": (
            ("HERO", 1, None, False), ("ABOUT", 8, None, False),
            ("GALLERY", 4, "gallery", False), ("TESTIMONIALS", 7, None, False),
            ("FOOTER", 2, None, False),
        ),
    },
    "portfolio": {
        "label": "Portfolio",
        "animation": "none",
        "font": "Plus Jakarta Sans",
        "sections": (
            ("HERO", 3, None, False), ("ABOUT", 1, None, False),
            ("GALLERY", 7, "project", False),
            ("TESTIMONIALS", 7, None, False), ("FOOTER", 1, None, False),
        ),
    },
    # The "News Outlet" (publisher) template was removed from the frontend on
    # 2026-08-05 (fe-serey-web f2f3b5023), so it is not offered to the AI either.
    # The frontend templates also use legacy hero/about style 2, which the style
    # picker no longer offers; they are mapped to the nearest picker styles that
    # render the same photo (hero 1 Backdrop, about 8 Social).
}


# Sections the AI may generate = sections the frontend can map AND render
# (LandingBuilderV2.js resolveTypeKey). Excluded although they exist in the
# frontend enum: NEWSLETTER (14) — use SUBSCRIPTION (13) for email signup — and
# CUSTOM (11), the Custom Code section (builder key "code"): the user writes its
# HTML & CSS in the code editor. The AI never creates, edits or deletes one;
# sanitize_content() puts the page's own type 11 sections back unchanged.
# (Type 11 was an older "Custom Section" with title/description/images until
# 2026-07-31; a type 11 section without `html` is legacy data from it.)
GENERATABLE_SECTIONS: tuple[str, ...] = (
    "HERO", "ABOUT", "GALLERY", "FOOTER", "VIDEO", "VISION", "BLOG", "TEAM",
    "FAQ", "TESTIMONIALS", "RANKING", "SUBSCRIPTION", "NOTES", "PODCAST", "TEXTBLOCK",
)

# The Custom Code section: type 11, builder key "code" (extra copies "code__2", …).
CODE_SECTION_TYPE = "CUSTOM"
CODE_SECTION_KEY = "code"


# ---------------------------------------------------------------------------
# Prompt builders — generate the knowledge blocks of the system prompt from
# the catalogs above so the prompt can never drift from the validators.
# ---------------------------------------------------------------------------

def build_type_id_block() -> str:
    ids = ", ".join(
        f"{SECTION_TYPE_NAME_TO_ID[name]} = {name}"
        for name in GENERATABLE_SECTIONS
        if name in SECTION_TYPE_NAME_TO_ID
    )
    return (
        f"Use numeric type IDs in all JSON output:\n  {ids}\n"
        '  TEXTBLOCK has NO numeric ID — emit "type": "TEXTBLOCK" (string) for it.\n'
        "  Do NOT use type 14 (NEWSLETTER) — use 13 (SUBSCRIPTION) for email signup sections."
    )


def build_section_registry_block() -> str:
    lines: list[str] = []
    for name in GENERATABLE_SECTIONS:
        type_id = SECTION_TYPE_NAME_TO_ID.get(name)
        id_label = f"{type_id} ({name})" if type_id else f'"{name}" (string type)'
        styles = ", ".join(str(v) for v in allowed_styles(name))
        lines.append(f"  {id_label} — {SECTION_FIELD_DOCS[name]}. Styles: {styles}.")
    return "\n".join(lines)


def build_palettes_block() -> str:
    rows = "\n".join(
        f"  {name:<18}: hero_bg={p['hero_bg']}  title={p['title']}  accent={p['accent']}  "
        f"section_bg={p['section_bg']}  bg_alt={p['bg_alt']}   ({p['vibe']})"
        for name, p in CURATED_PALETTES.items()
    )
    return rows


def build_fonts_block() -> str:
    return ", ".join(FONT_OPTIONS)


def build_color_keys_block() -> str:
    return "\n".join(
        f"  {name}: {', '.join(keys)}"
        for name, keys in SECTION_COLOR_KEYS.items()
        if name in GENERATABLE_SECTIONS
    )


def _validate() -> None:
    """Catch drift between the catalog JSON and everything keyed off it."""
    for name, section in FE_SECTIONS.items():
        assert SECTION_TYPE_ID_MAP.get(section["type"]) == name, (
            f"catalog JSON: {name} is type {section['type']}, SECTION_TYPE_ID_MAP has "
            f"{SECTION_TYPE_ID_MAP.get(section['type'])!r}"
        )
        assert name in GENERATABLE_SECTIONS, f"catalog JSON section {name} is missing from GENERATABLE_SECTIONS"
    for name, template in FRONTEND_TEMPLATES.items():
        for section, style, subtype, _hidden in template["sections"]:
            valid = PRODUCT_SUBTYPE_STYLES if subtype == "product" else allowed_styles(section)
            assert style in valid, f"FRONTEND_TEMPLATES[{name}]: {section} style {style} not in {sorted(valid)}"


_validate()
