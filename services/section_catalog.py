# Single source of truth for everything the AI builder must know about the
# Serey V2 landing-page frontend. Every constant here mirrors a constant in
# fe-serey-web — the frontend file/name is noted next to each block.
# When the frontend gains a section, style, font, or field, update it HERE
# and the system prompt / validators pick it up automatically.

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Section types
# Mirrors: fe-serey-web src/config/constants.js LANDING_PAGE_TEMPLATE_TYPE_V2
# and LandingBuilderV2.js resolveTypeKey().
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
}

SECTION_TYPE_NAME_TO_ID: dict[str, int] = {v: k for k, v in SECTION_TYPE_ID_MAP.items()}

# String-only section types (no numeric ID; serialized as the string itself)
STRING_ONLY_SECTION_TYPES: tuple[str, ...] = ("TEXTBLOCK",)

ALL_SECTION_TYPES: tuple[str, ...] = tuple(SECTION_TYPE_ID_MAP.values()) + STRING_ONLY_SECTION_TYPES

# ---------------------------------------------------------------------------
# Layout styles per section — value, label, description.
# Mirrors: LandingBuilderV2.js SectionLayoutStylePicker (the visual style strip
# the user actually sees) — that picker, not the legacy SECTION_STYLE_OPTIONS
# dropdown, is the source of truth for which style numbers exist.
# Order matches the frontend picker; the FIRST value is the default style.
# NOTE: the picker labels its chips by POSITION for ABOUT and TESTIMONIALS
# (chip "1." is not style 1) — always use the `value` here, never the chip number.
# The old full-bleed "style 99" variant no longer exists: any section can carry
# a background image via bg_image_url on any style.
# ---------------------------------------------------------------------------

SECTION_STYLES: dict[str, tuple[tuple[int, str, str], ...]] = {
    "HERO": (
        (1, "Backdrop", "Text on the left over a full-bleed background image, no overlay"),
        (3, "Centered", "Title and description centered on a solid background color, no image"),
        (4, "Magazine", "Editorial-style layout with bold typography and image panel"),
        (5, "Mag Cover", "Magazine cover style with horizontal rules and editorial typography"),
        (6, "Card Overlay", "Padded dark card with image background, overlay gradient, and centered bold text"),
    ),
    "ABOUT": (
        (8, "Social", "Image on left, title and description on right with a row of social links below"),
        (1, "Panel", "Colored accent panel on the left with the text beside it, no image"),
        (4, "Text Only", "Centered title and description, no image"),
        (9, "Split Panel", "Two columns: description on a light panel, title on a slightly darker panel"),
        (13, "Spotlight", "Portrait image with a star-rating badge, title/description with a Learn More button and a small accent photo — fixed layout"),
    ),
    "GALLERY": (
        (1, "Classic", "Uniform 3-column image grid"),
        (2, "Feature R", "2x2 grid left with a large featured image on the right"),
        (3, "Bento", "Two rows of uneven-width mosaic tiles with name captions — auto-slides in groups of 6 when there are more"),
        (4, "Polaroid", "Polaroid-style photo cards with slight tilt and shadow"),
        (5, "Coverflow", "Center image large and centered, fading/shrinking out on each side — slides one at a time"),
        (6, "Slideshow", "Full-width slideshow with arrows, dots, and autoplay"),
        (7, "Wall", "Tight no-gap grid with many small cells"),
        (8, "Feature Strip", "Large featured image on the left with a narrow vertical stack of 4 thumbnails on the right"),
        (9, "Mosaic Grid", "Top row of 4 equal photos; bottom row has the 5th photo large with the 6th/7th stacked beside it"),
    ),
    "VIDEO": (
        (1, "Classic", "Title and description above a single centered video player"),
        (2, "Split", "Text column on one side, video player on the other"),
        (3, "Showcase", "One large featured video with a sidebar list of the others"),
        (4, "Film Review", "Editorial film-review layout: rules, eyebrow label, big title, then a row of players"),
        (5, "Feature", "Click-to-play video thumbnail on one side, title and description on the other"),
        (6, "Grid", "Up to 4 click-to-play video thumbnails in a 2x2 card grid, each with its own title"),
    ),
    "VISION": (
        (1, "Cards", "Goal, Vision, Mission each in a separate colored card"),
        (2, "3 Columns", "Three equal columns side by side"),
        (3, "Icon Rows", "Rows with icons, titles, and descriptions"),
        (4, "Steps Dark", "Dark background with numbered step-style layout"),
        (5, "Feature Grid", "Feature-grid with icon tiles and short descriptions"),
        (6, "Split Panel", "Large panel split between goal/vision/mission vertically"),
        (7, "Text Only", "Plain stacked title and description text, no cards or icons"),
    ),
    "BLOG": (
        (1, "Grid", "3-column card grid of blog post previews"),
        (2, "List", "Vertical list of posts with thumbnail on the left"),
        (3, "Magazine", "Featured large post on top, smaller posts below"),
        (4, "Minimal", "Text-only list, no thumbnails — clean and fast"),
        (5, "Overlay", "Image cards with text overlaid on a dark gradient"),
        (6, "Editorial", "Newspaper editorial-style with mixed large/small blocks"),
        (7, "Mag Front Page", "Front-page layout: one large featured post beside a numbered sidebar list"),
        (8, "Editorial Strip", "Title and subtitle above a rule, three square images with captions below"),
        (9, "News Row", 'Title with a "View all news" link, three dated cards with excerpts below'),
    ),
    "TEAM": (
        (1, "Grid", "Uniform grid of member photos with name and role"),
        (2, "Cards", "Cards with photo, name, role, and short bio"),
        (3, "Banner", "Wide banner-style strips for each member"),
        (5, "Color Card", "Colored card with the photo bleeding to the edges and a name/role tag overlapping the bottom"),
        (6, "Circle Bio", "Circular photo with name, a colored role badge, and a short bio underneath"),
    ),
    "FAQ": (
        (1, "Accordion", "Classic expand/collapse accordion for each question"),
        (2, "Two Col", "Questions and answers in two side-by-side columns"),
        (3, "Split", "Questions on the left panel, answers on the right"),
        (4, "Left Border", "Each item has a colored left border accent"),
        (5, "Cards", "Each Q&A pair in its own card"),
        (6, "Numbered", "Numbered Q&A list with large question numbers"),
        (7, "Q&A Interview", "Interview-style layout: eyebrow label and title above rule-separated question/answer pairs"),
    ),
    "TESTIMONIALS": (
        (1, "Cards", "Quote cards with avatar, name, and star rating"),
        (7, "Cards (No Image)", "Card-style quotes with name/role and no avatar image"),
        (9, "Large Quote", "One large centered quote with the author photo below"),
        (10, "Pull Quote", "Large italic editorial pull-quote with prev/next navigation and accent-colored dots"),
        (6, "Bubble", "Speech-bubble quote cards with a tail, avatar and name underneath"),
        (11, "Star Cards", "Staggered 3-card grid with a star rating, eyebrow label, and bold heading above"),
        (12, "Split Dark", "Full-width photo on one side, dark panel on the other with stars, quote and name"),
    ),
    "CUSTOM": (
        (1, "Split Right", "Text on left, image on right"),
        (2, "Split Left", "Image on left, text on right"),
        (3, "Centered", "Centered text and image, stacked vertically"),
        (4, "Banner", "Full-width banner with overlaid text and optional button"),
        (5, "Card", "Content inside a centered card with shadow"),
        (6, "Highlight", "Highlighted accent block with two images and text"),
    ),
    "RANKING": (
        (1, "List", "Ranked vertical list with position numbers"),
        (2, "Podium", "Top 3 on a podium, rest in a list below"),
        (3, "Cards", "Author cards in a grid with avatar and stats"),
        (4, "Circles", "Circular avatar bubbles arranged in a row"),
        (5, "Leaderboard", "Editorial leaderboard: eyebrow label and title above numbered rows with avatar, name and post count"),
    ),
    "SUBSCRIPTION": (
        (1, "Centered Card", "Centered bordered card with title, description and form"),
        (2, "Cinematic", "Full-width section with large background, gradient overlay and eyebrow label"),
        (3, "Split Panel", "Accent-colored left panel with text, white right panel with form"),
        (4, "Benefits + Form", "Bullet benefit list on the left, subscription form card on the right"),
        (5, "Checklist + Card", "Equal two-column split: title and a checklist of benefits on the left, a bordered form card on the right"),
        (6, "Split Image", "Equal two-column split: title, description and form on the left, a full-height photo on the right"),
    ),
    "FOOTER": (
        (1, "Dark Navy", "Dark navy/black background with white text and social icons"),
        (2, "Minimal", "Light minimal footer with just contact info and links"),
        (3, "Columns", "Multi-column footer with contact, socials, and logo"),
        (4, "Gradient Split", "Dark gradient background with logo and socials on left, contact on right, social icons as glowing circles"),
        (5, "Editorial", "Bold top border, brand and socials in a top row, contact chips and copyright in bottom row — clean magazine style"),
    ),
    "NOTES": (
        (1, "Slider", "Dark band with a 3-up slider of trending note cards (author, text, image)"),
        (2, "Masonry", "Pinterest-style wall of all notes in staggered columns"),
        (3, "Spotlight", "One large featured note on the left with a compact list of the next notes on the right"),
    ),
    # Not in the frontend style picker — single-layout sections.
    "NEWSLETTER": ((1, "Default", "Simple newsletter signup block"),),
    "TEXTBLOCK": ((1, "Default", "Free-form rich text block"),),
}


def allowed_styles(section_type: str) -> tuple[int, ...]:
    return tuple(v for v, _label, _desc in SECTION_STYLES.get(section_type, ((1, "", ""),)))


def style_label(section_type: str, style: int) -> str:
    for value, label, _desc in SECTION_STYLES.get(section_type, ()):
        if value == style:
            return label
    return f"Style {style}"


# ---------------------------------------------------------------------------
# Layout style preference weights — which styles the AI should reach for when
# it picks or randomizes a section's layout. Unlike SECTION_STYLES (a mirror of
# the frontend) this is a product preference: some layouts simply photograph
# better on a generated page than others.
#   high   — default/first choice, use most often
#   low    — only when the user explicitly asks for it, or as a last resort
#   medium — everything else, including sections absent from this table
# ---------------------------------------------------------------------------

STYLE_WEIGHTS: dict[str, dict[str, tuple[int, ...]]] = {
    "ABOUT":        {"high": (8, 9), "low": (1,)},
    "TESTIMONIALS": {"high": (1, 9, 10, 6, 11, 12), "low": ()},
    "FOOTER":       {"high": (2, 5), "low": ()},
    "GALLERY":      {"high": (1, 2, 3, 4), "low": ()},
    "VIDEO":        {"high": (1, 2, 3, 4), "low": ()},
    "VISION":       {"high": (2, 5, 7), "low": ()},
    "BLOG":         {"high": (1, 2, 3, 4, 5, 6, 7, 8, 9), "low": ()},
    "TEAM":         {"high": (1, 6), "low": (2, 3)},
    "FAQ":          {"high": (1, 2, 3, 4, 5, 6, 7), "low": ()},
    "SUBSCRIPTION": {"high": (2, 4), "low": ()},
    "NOTES":        {"high": (1, 2, 3), "low": ()},
}


def style_weight(section_type: str, style: int) -> str:
    weights = STYLE_WEIGHTS.get(section_type)
    if not weights:
        return "medium"
    if style in weights.get("high", ()):
        return "high"
    if style in weights.get("low", ()):
        return "low"
    return "medium"


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
        "HERO": {"image_url": (1, 4, 5, 6)},
        "ABOUT": {"image_url": (8, 13), "image_url_2": (13,)},
        "CUSTOM": {"image_url": (1, 2, 3, 4, 5, 6), "image_url_2": (6,)},
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
    ("custom", "image_url"): "Custom Section Image",
    ("custom", "image_url_2"): "Custom Section Image 2",
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

# Mirrors LandingBuilderV2.js ANIM_OPTIONS (top-level animation_style).
ANIMATION_STYLES: tuple[str, ...] = ("none", "fade", "slide-up", "slide-left", "blur")

# Mirrors Shared/LandingPageV2/imageShapes.js IMAGE_SHAPE_OPTIONS
# (per-section image_shape field; "" = default/square).
IMAGE_SHAPES: tuple[str, ...] = (
    "square", "rounded", "circle", "arch", "diamond", "hexagon", "blob", "star",
)

# Per-section theme variants the renderers understand ("" = default).
SECTION_THEMES: tuple[str, ...] = ("", "editorial")

# ---------------------------------------------------------------------------
# Colors — per-section color keys. Mirrors LandingBuilderV2.js SECTION_COLOR_CONFIG.
# All keys are hex strings inside the section "colors" object.
# ---------------------------------------------------------------------------

SECTION_COLOR_KEYS: dict[str, tuple[str, ...]] = {
    "HERO": ("title", "accent", "subtitle", "body", "bg"),
    "ABOUT": ("title", "accent", "body", "bg"),
    "GALLERY": ("title", "accent", "body", "bg"),
    "VIDEO": ("title", "accent", "body", "bg"),
    "VISION": ("title", "accent", "body", "bg", "goal_color", "vision_color", "mission_color"),
    "BLOG": ("title", "accent", "body", "bg"),
    "TEAM": ("title", "accent", "bg"),
    "FAQ": ("title", "accent", "bg"),
    "TESTIMONIALS": ("title", "body", "accent", "bg"),
    "CUSTOM": ("title", "body", "accent", "bg"),
    "RANKING": ("title", "bg"),
    "NOTES": ("title", "body", "bg"),
    "SUBSCRIPTION": ("bg", "card_bg", "accent"),
    "FOOTER": ("title", "bg", "accent"),
    "NEWSLETTER": ("title", "bg", "accent"),
    "TEXTBLOCK": ("title", "body", "bg"),
}

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
    "CUSTOM": "title, description, button_label, button_url, image_url, image_url_2, image_url_3, image_shape",
    "RANKING": "title, description, authors (always leave as []) — top authors are auto-fetched",
    "NOTES": 'title, description, feed_type ("trending" | "latest") — community notes are auto-fetched, never invent them',
    "SUBSCRIPTION": 'title, description, button_label ("Subscribe"), placeholder_text, newsletter_provider ("" | "kit" | "email_octopus"), kit_embed_script, email_octopus_embed_script — leave provider/embed fields "" unless the user provides them',
    "TEXTBLOCK": "title, description, content (free-form rich text) — emit type as the string \"TEXTBLOCK\" (it has no numeric ID)",
}

# Gallery subtypes the frontend renders (GALLERY_SUBTYPE_LABELS / ProductSection).
GALLERY_SUBTYPES: tuple[str, ...] = ("gallery", "product", "project")

# GALLERY subtype 'product' renders via ProductSection and has its OWN style
# picker: 1 Duo, 2 List, 4 Editorial, 5 Shop, 6 Duo (Text Outside). Any other
# number falls back to style 1. The photo subtypes ('gallery'/'project') use
# the full GALLERY style list above.
PRODUCT_SUBTYPE_STYLES: tuple[int, ...] = (1, 2, 4, 5, 6)

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


def build_templates_block() -> str:
    lines: list[str] = []
    for name, t in FRONTEND_TEMPLATES.items():
        parts = ", ".join(
            f"{sec} s{style}" + (f" ({subtype})" if subtype else "") + (" [hidden]" if hidden else "")
            for sec, style, subtype, hidden in t["sections"]
        )
        lines.append(f"  {name} ({t['label']}): font \"{t['font']}\", animation {t['animation']} — {parts}")
    return "\n".join(lines)


# Style guidance for sections the onboarding flow appends BEYOND a template's
# base structure (the "Add more sections?" picker splices them before FOOTER).
# Keyed by template id; each value: (styles that fit the template's vibe,
# styles to avoid). Mirrors the cheat sheet in BUILDER_V2_AI_BACKEND.md.
TEMPLATE_EXTRA_STYLE_GUIDE: dict[str, dict[str, str]] = {
    "ecommerce": {
        "use": "bold high-contrast layouts — VISION s2, TEAM s5, FAQ s1, SUBSCRIPTION s4 (product galleries stay s1)",
        "avoid": "soft serif/editorial styles (magazine and pull-quote layouts)",
    },
    "creator": {
        "use": "dark modern visual layouts — GALLERY s5/s6, VIDEO s3, VISION s4, SUBSCRIPTION s2",
        "avoid": "light pastel or plain 3-column text styles",
    },
    "portfolio": {
        "use": "clean white minimal text-led layouts — ABOUT s9, FAQ s3, VISION s5, TESTIMONIALS s9",
        "avoid": "cinematic dark styles and product-card shelves",
    },
}


def build_template_extras_block() -> str:
    lines: list[str] = []
    for name, g in TEMPLATE_EXTRA_STYLE_GUIDE.items():
        lines.append(f"  {name}: use {g['use']}; avoid {g['avoid']}")
    return "\n".join(lines)


# Sections the AI may generate = sections the frontend can map AND render
# (LandingBuilderV2.js resolveTypeKey). Excluded although they exist in the
# frontend enum: NEWSLETTER (14) — use SUBSCRIPTION (13) for email signup — and
# CUSTOM (11), which has no mapping or renderer, so the frontend silently drops it.
GENERATABLE_SECTIONS: tuple[str, ...] = (
    "HERO", "ABOUT", "GALLERY", "FOOTER", "VIDEO", "VISION", "BLOG", "TEAM",
    "FAQ", "TESTIMONIALS", "RANKING", "SUBSCRIPTION", "NOTES", "TEXTBLOCK",
)


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


def build_style_descriptions_block() -> str:
    blocks: list[str] = []
    for name in GENERATABLE_SECTIONS:
        styles = SECTION_STYLES.get(name)
        if not styles or name == "TEXTBLOCK":
            continue
        rows = "\n".join(f"  {value} = {label} — {desc}" for value, label, desc in styles)
        blocks.append(f"{name} styles:\n{rows}")
    return "\n\n".join(blocks)


def build_style_weights_block() -> str:
    """Renders STYLE_WEIGHTS as a High/Medium/Low table for the system prompt."""
    blocks: list[str] = []
    for name in GENERATABLE_SECTIONS:
        styles = SECTION_STYLES.get(name)
        if not styles or name == "TEXTBLOCK":
            continue
        buckets: dict[str, list[str]] = {"High": [], "Medium": [], "Low": []}
        for value, label, _desc in styles:
            buckets[style_weight(name, value).capitalize()].append(f"{label} ({value})")
        if not STYLE_WEIGHTS.get(name):
            blocks.append(f"  {name}: no preference — treat every style as Medium")
            continue
        if not buckets["Medium"] and not buckets["Low"]:
            blocks.append(f"  {name}: High — all styles equally")
            continue
        rows = "\n".join(
            f"      {tier:<7}{', '.join(items)}" for tier, items in buckets.items() if items
        )
        blocks.append(f"  {name}:\n{rows}")
    return "\n".join(blocks)


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
    """Catch drift between SECTION_STYLES and everything keyed off it."""
    for section, weights in STYLE_WEIGHTS.items():
        allowed = set(allowed_styles(section))
        for tier in ("high", "low"):
            unknown = set(weights.get(tier, ())) - allowed
            assert not unknown, f"STYLE_WEIGHTS[{section}].{tier}: unknown styles {sorted(unknown)}"
    for name, template in FRONTEND_TEMPLATES.items():
        for section, style, subtype, _hidden in template["sections"]:
            valid = PRODUCT_SUBTYPE_STYLES if subtype == "product" else allowed_styles(section)
            assert style in valid, f"FRONTEND_TEMPLATES[{name}]: {section} style {style} not in {sorted(valid)}"


_validate()
