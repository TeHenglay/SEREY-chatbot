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
}

SECTION_TYPE_NAME_TO_ID: dict[str, int] = {v: k for k, v in SECTION_TYPE_ID_MAP.items()}

# String-only section types (no numeric ID; serialized as the string itself)
STRING_ONLY_SECTION_TYPES: tuple[str, ...] = ("TEXTBLOCK",)

ALL_SECTION_TYPES: tuple[str, ...] = tuple(SECTION_TYPE_ID_MAP.values()) + STRING_ONLY_SECTION_TYPES

# Style 99 = full-bleed "Background Image" variant available on every section.
BACKGROUND_IMAGE_STYLE = 99

# ---------------------------------------------------------------------------
# Layout styles per section — value, label, description.
# Mirrors: LandingBuilderV2.js SECTION_STYLE_OPTIONS (labels/descriptions verbatim).
# Order matches the frontend picker; the FIRST value is the default style.
# ---------------------------------------------------------------------------

SECTION_STYLES: dict[str, tuple[tuple[int, str, str], ...]] = {
    "HERO": (
        (1, "Split", "Text on left, image on right — two-column layout"),
        (2, "Cinematic", "Full-width dramatic hero with large background image and overlay text"),
        (3, "Centered", "Title and description centered on a solid background color, no image"),
        (4, "Magazine", "Editorial-style layout with bold typography and image panel"),
        (5, "Mag Cover", "Magazine cover style with horizontal rules and editorial typography"),
        (6, "Card Overlay", "Padded dark card with image background, overlay gradient, and centered bold text"),
        (99, "Background Image", "Full-width background image with dramatic overlay and centered bold typography"),
    ),
    "ABOUT": (
        (1, "Classic", "Text on left, image on right"),
        (2, "Round L", "Circular image on the left, text on the right"),
        (3, "Card R", "Image in a card on the right with a floating shadow effect"),
        (4, "Text L", "Text-only layout aligned to the left, no image"),
        (5, "Panel", "Colored background panel with text and image side by side"),
        (6, "Panel T", "Full-width top panel with image above and text below"),
        (7, "Feature Spread", "Editorial image-left / text-right body layout"),
        (99, "Background Image", "Full-width background image with centered image thumbnail and text overlay"),
    ),
    "GALLERY": (
        (1, "Classic", "Uniform 3-column image grid"),
        (2, "Feature R", "2x2 grid left with a large featured image on the right"),
        (3, "Masonry", "Masonry column layout with mixed image heights"),
        (4, "Spotlight", "One hero item on top with a row of smaller items below"),
        (5, "Strip", "Horizontal strip of images with side-by-side tiles"),
        (6, "Polaroid", "Polaroid-style photo cards with slight tilt and shadow"),
        (7, "Cinematic", "Stacked wide images in a cinematic 16:9 feel"),
        (8, "Triptych", "Three tall equal columns"),
        (9, "Overlap", "Overlapping card layout with depth and shadow"),
        (11, "Wall", "Tight no-gap grid with many small cells"),
        (12, "Photo Essay", "Editorial photo essay layout with rules and captions"),
        (99, "Background Image", "Gallery grid floating over a dramatic background image overlay"),
    ),
    "VIDEO": (
        (1, "Classic", "Standard centered video player with title above"),
        (2, "Dark", "Dark background section with prominent video embed"),
        (3, "Split", "Video on one side, text description on the other"),
        (4, "Cards", "Multiple videos in a card grid layout"),
        (5, "Showcase", "Large featured video with a highlighted frame"),
        (99, "Background Image", "Centered video player on a full-bleed background image with overlay"),
    ),
    "VISION": (
        (1, "Cards", "Goal, Vision, Mission each in a separate colored card"),
        (2, "3 Columns", "Three equal columns side by side"),
        (3, "Icon Rows", "Rows with icons, titles, and descriptions"),
        (4, "Steps Dark", "Dark background with numbered step-style layout"),
        (5, "Feature Grid", "Feature-grid with icon tiles and short descriptions"),
        (6, "Split Panel", "Large panel split between goal/vision/mission vertically"),
        (99, "Background Image", "Goal, Vision, Mission as glass cards over a background image"),
    ),
    "BLOG": (
        (1, "Grid", "3-column card grid of blog post previews"),
        (2, "List", "Vertical list of posts with thumbnail on the left"),
        (3, "Magazine", "Featured large post on top, smaller posts below"),
        (4, "Minimal", "Text-only list, no thumbnails — clean and fast"),
        (5, "Overlay", "Image cards with text overlaid on a dark gradient"),
        (6, "Editorial", "Newspaper editorial-style with mixed large/small blocks"),
        (99, "Background Image", "Post cards floating over a full-width background image with dark overlay"),
    ),
    "TEAM": (
        (1, "Grid", "Uniform grid of member photos with name and role"),
        (2, "Cards", "Cards with photo, name, role, and short bio"),
        (4, "List", "Horizontal rows — photo left, info right"),
        (5, "Banner", "Wide banner-style strips for each member"),
        (6, "Spotlight", "One featured member large, rest in a row"),
        (7, "Staggered", "Alternating left/right photo-text rows"),
        (99, "Background Image", "Team member glass cards over a dramatic background image"),
    ),
    "FAQ": (
        (1, "Accordion", "Classic expand/collapse accordion for each question"),
        (2, "Two Col", "Questions and answers in two side-by-side columns"),
        (3, "Split", "Questions on the left panel, answers on the right"),
        (4, "Left Border", "Each item has a colored left border accent"),
        (5, "Cards", "Each Q&A pair in its own card"),
        (6, "Numbered", "Numbered Q&A list with large question numbers"),
        (99, "Background Image", "FAQ items as glass cards over a full-width background image"),
    ),
    "TESTIMONIALS": (
        (1, "Cards", "Quote cards with avatar, name, and star rating"),
        (7, "Cards (No Image)", "Card-style quotes with name/role and no avatar image"),
        (3, "Side by Side", "Two testimonials shown side by side"),
        (4, "Minimal List", "Simple text list of quotes with attribution"),
        (5, "Left Border", "Quotes with a vertical colored left border"),
        (6, "Dark", "Dark background section with light text quotes"),
        (99, "Background Image", "Quote cards with frosted-glass effect over a background image"),
    ),
    "CUSTOM": (
        (1, "Split Right", "Text on left, image on right"),
        (2, "Split Left", "Image on left, text on right"),
        (3, "Centered", "Centered text and image, stacked vertically"),
        (4, "Banner", "Full-width banner with overlaid text and optional button"),
        (5, "Card", "Content inside a centered card with shadow"),
        (6, "Highlight", "Highlighted accent block with two images and text"),
        (99, "Background Image", "Centered content and image on a dramatic full-width background image"),
    ),
    "RANKING": (
        (1, "List", "Ranked vertical list with position numbers"),
        (2, "Podium", "Top 3 on a podium, rest in a list below"),
        (3, "Cards", "Author cards in a grid with avatar and stats"),
        (4, "Circles", "Circular avatar bubbles arranged in a row"),
        (99, "Background Image", "Leaderboard list with glass cards over a background image"),
    ),
    "SUBSCRIPTION": (
        (1, "Centered Card", "Centered bordered card with title, description and form — Path of Change style"),
        (2, "Side by Side", "Text on the left, email form on the right in a two-column layout"),
        (3, "Cinematic", "Full-width section with large background, gradient overlay and eyebrow label"),
        (4, "Split Panel", "Accent-colored left panel with text, white right panel with form"),
        (5, "Bold Typographic", "Large typography with a decorative accent line above the title"),
        (6, "Benefits + Form", "Bullet benefit list on the left, subscription form card on the right"),
        (7, "Compact Bar", "Slim full-width accent-colored bar with inline title and form"),
        (99, "Background Image", "Centered subscription form on a full-width background image with dark overlay"),
    ),
    "FOOTER": (
        (1, "Dark Navy", "Dark navy/black background with white text and social icons"),
        (2, "Minimal", "Light minimal footer with just contact info and links"),
        (3, "Columns", "Multi-column footer with contact, socials, and logo"),
        (4, "Gradient Split", "Dark gradient background with logo and socials on left, contact on right, social icons as glowing circles"),
        (5, "Editorial", "Bold top border, brand and socials in a top row, contact chips and copyright in bottom row — clean magazine style"),
        (99, "Background Image", "Centered footer content over a background image with dark overlay"),
    ),
    # Not in the frontend style picker — single-layout sections.
    "NEWSLETTER": ((1, "Default", "Simple newsletter signup block"),),
    "TEXTBLOCK": ((1, "Default", "Free-form rich text block"),),
}


def allowed_styles(section_type: str) -> tuple[int, ...]:
    return tuple(v for v, _label, _desc in SECTION_STYLES.get(section_type, ((1, "", ""),)))


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
        # Mirrors IMAGE_FIELD_STYLE_RULES — hero style 3 and all style-99
        # variants are text/background-only for the scalar image slot.
        "HERO": {"image_url": (1, 2, 4, 5, 6)},
        "ABOUT": {"image_url": (1, 2, 3, 5, 7)},
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
    "ABOUT": 'title, subtitle, description, image_url, image_ratio ("16:9"), image_width (null), image_height (null), image_shape',
    "GALLERY": 'title, description, images[{image_url, name, description}], section_subtype ("product" = product/services/features cards with name+description; "gallery" = plain photo grid; "project" = portfolio project cards). Every image item MUST have image_url (""), name, and description.',
    "FOOTER": 'title, description, phone, email, location, logo_url, contact_heading, social_heading, privacy_url, terms_url, social_links[{"type":"facebook"|"instagram"|"telegram","handle":"..."}]',
    "VIDEO": "title, description, videos[{url, title, thumbnail}]",
    "VISION": "title, description, goals_title, goals_description, vision_title, vision_description, mission_title, mission_description, image_url",
    "BLOG": 'title, subtitle, description, feed_type ("trending" | "latest") — posts are auto-fetched, never invent them',
    "TEAM": "title, description, members[{name, role, image_url}]",
    "FAQ": "title, faq_items[{question, answer}]",
    "TESTIMONIALS": "title, testimonial_items[{name, role, content, image_url}] (max 6)",
    "CUSTOM": "title, description, button_label, button_url, image_url, image_url_2, image_url_3, image_shape",
    "RANKING": "title, description, authors (always leave as []) — top authors are auto-fetched",
    "SUBSCRIPTION": 'title, description, button_label ("Subscribe"), placeholder_text, newsletter_provider ("" | "kit" | "email_octopus"), kit_embed_script, email_octopus_embed_script — leave provider/embed fields "" unless the user provides them',
    "TEXTBLOCK": "title, description, content (free-form rich text) — emit type as the string \"TEXTBLOCK\" (it has no numeric ID)",
}

# Gallery subtypes the frontend renders (GALLERY_SUBTYPE_LABELS / ProductSection).
GALLERY_SUBTYPES: tuple[str, ...] = ("gallery", "product", "project")

# GALLERY subtype 'product' renders via ProductSection, which only implements
# styles 1-5 (any other number falls back to style 1). The photo subtypes
# ('gallery'/'project') use the full GALLERY style list above.
PRODUCT_SUBTYPE_STYLES: tuple[int, ...] = (1, 2, 3, 4, 5)

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
            ("HERO", 2, None, False), ("ABOUT", 2, None, False),
            ("GALLERY", 1, "product", False), ("TESTIMONIALS", 7, None, False),
            ("FAQ", 1, None, False), ("FOOTER", 4, None, False),
        ),
    },
    "creator": {
        "label": "Content Creator",
        "animation": "blur",
        "font": "Inter",
        "sections": (
            ("HERO", 1, None, False), ("ABOUT", 2, None, False),
            ("GALLERY", 6, "gallery", False), ("TESTIMONIALS", 7, None, False),
            ("CUSTOM", 3, None, False), ("FOOTER", 2, None, False),
        ),
    },
    "portfolio": {
        "label": "Portfolio",
        "animation": "none",
        "font": "Plus Jakarta Sans",
        "sections": (
            ("HERO", 3, None, False), ("ABOUT", 1, None, False),
            ("GALLERY", 11, "project", False), ("CUSTOM", 2, None, False),
            ("TESTIMONIALS", 7, None, False), ("FOOTER", 1, None, False),
        ),
    },
    "publisher": {
        "label": "Publisher",
        "animation": "slide-left",
        "font": "Lora",
        "sections": (
            ("HERO", 5, None, False), ("ABOUT", 7, None, False),
            ("BLOG", 6, None, False), ("VIDEO", 1, None, True),
            ("GALLERY", 3, "gallery", False), ("TEAM", 4, None, False),
            ("RANKING", 1, None, False), ("FOOTER", 5, None, False),
        ),
    },
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
        "use": "bold high-contrast layouts — GALLERY product s5, VISION s2, TEAM s5, FAQ s1, SUBSCRIPTION s7",
        "avoid": "soft serif/editorial styles (style-7 panels, magazine layouts)",
    },
    "creator": {
        "use": "dark modern visual layouts — GALLERY s6/s9, VIDEO s2, VISION s4, SUBSCRIPTION s3",
        "avoid": "light pastel or plain 3-column text styles",
    },
    "portfolio": {
        "use": "clean white minimal text-led layouts — ABOUT s5, CUSTOM s2, FAQ s3, VISION s5",
        "avoid": "cinematic dark styles and product-card shelves",
    },
    "publisher": {
        "use": "editorial serif layouts — any style-7 editorial variant, GALLERY s3/s12, TEAM s4, FAQ s2",
        "avoid": "product cards and dark e-commerce styles",
    },
}


def build_template_extras_block() -> str:
    lines: list[str] = []
    for name, g in TEMPLATE_EXTRA_STYLE_GUIDE.items():
        lines.append(f"  {name}: use {g['use']}; avoid {g['avoid']}")
    return "\n".join(lines)


# Sections the AI may generate. NEWSLETTER is excluded — the current frontend
# cannot parse numeric type 14; use SUBSCRIPTION (13) for email signup.
GENERATABLE_SECTIONS: tuple[str, ...] = (
    "HERO", "ABOUT", "GALLERY", "FOOTER", "VIDEO", "VISION", "BLOG", "TEAM",
    "FAQ", "TESTIMONIALS", "CUSTOM", "RANKING", "SUBSCRIPTION", "TEXTBLOCK",
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
