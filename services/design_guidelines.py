# Design intelligence for the AI builder — font pairings, complete design
# recipes, visual rhythm, and copywriting rules. Unlike section_catalog.py
# (a strict mirror of the frontend), this module is OUR design opinion layer:
# it only references fonts/styles/palettes that exist in the catalog, but the
# combinations and rules here are curated by hand to make generated pages
# look intentionally designed rather than templated.

from __future__ import annotations

from services.section_catalog import (
    ANIMATION_STYLES,
    CURATED_PALETTES,
    FONT_OPTIONS,
    SECTION_STYLES,
)

# ---------------------------------------------------------------------------
# Font pairings — display font for titles + workhorse font for body text.
# The pair is applied via blueprint "font" (body) + hero text_styles
# title_font (display); the frontend propagates hero fonts to all sections.
# ---------------------------------------------------------------------------

FONT_PAIRINGS: dict[str, dict[str, str]] = {
    "editorial-luxury":  {"title": "Playfair Display",   "body": "Source Sans 3",  "vibe": "luxury, editorial, fashion, premium"},
    "warm-artisan":      {"title": "DM Serif Display",   "body": "Nunito Sans",    "vibe": "restaurant, cafe, artisan, handmade"},
    "classic-serif":     {"title": "Cormorant Garamond", "body": "Lato",           "vibe": "heritage, literary, elegant, wedding"},
    "modern-tech":       {"title": "Space Grotesk",      "body": "Inter",          "vibe": "tech, SaaS, startup, crypto"},
    "clean-corporate":   {"title": "Montserrat",         "body": "Open Sans",      "vibe": "corporate, professional services, finance"},
    "friendly-community":{"title": "Poppins",            "body": "Karla",          "vibe": "community, social, education, family"},
    "bold-statement":    {"title": "Bebas Neue",         "body": "Manrope",        "vibe": "gym, sports, events, streetwear"},
    "creative-studio":   {"title": "Syne",               "body": "Work Sans",      "vibe": "agency, portfolio, design studio, art"},
    "quiet-minimal":     {"title": "Manrope",            "body": "Inter",          "vibe": "minimal, architecture, photography"},
    "khmer-modern":      {"title": "Kantumruy Pro",      "body": "Kantumruy Pro",  "vibe": "Khmer-language sites, Cambodia local business"},
    "khmer-classic":     {"title": "Battambang",         "body": "Kantumruy Pro",  "vibe": "Khmer traditional, culture, heritage"},
}

# ---------------------------------------------------------------------------
# Design recipes — complete, coherent looks. Each recipe locks a palette,
# a font pairing, an animation, and a set of section styles that work
# TOGETHER. Picking a recipe and following it end-to-end is what makes a
# page look designed instead of assembled.
# Only uses palette names from CURATED_PALETTES, pairing names from
# FONT_PAIRINGS, and style numbers from SECTION_STYLES.
# ---------------------------------------------------------------------------

DESIGN_RECIPES: dict[str, dict] = {
    "corporate-trust": {
        "when": "corporate, SaaS, finance, professional services, agencies pitching enterprises",
        "palette": "navy-professional",
        "fonts": "clean-corporate",
        "animation": "fade",
        "styles": {"hero": 1, "about": 8, "gallery": 2, "vision": 5, "faq": 1, "testimonials": 11, "custom": 1, "footer": 3},
        "notes": "Confident and orderly. Square/rounded images only. Accent used for buttons and underlines, never large fills except one CUSTOM highlight.",
    },
    "artisan-warmth": {
        "when": "restaurants, cafes, bakeries, handmade goods, local food brands",
        "palette": "warm-amber",
        "fonts": "warm-artisan",
        "animation": "fade",
        "styles": {"hero": 5, "about": 8, "gallery": 4, "testimonials": 10, "faq": 5, "custom": 5, "footer": 5},
        "notes": "Cozy and tactile. Use image_shape 'arch' on about/custom images. Polaroid gallery. Editorial footer. Descriptions should be sensory (taste, smell, craft).",
    },
    "editorial-magazine": {
        "when": "blogs, news, publishers, media platforms, writers, magazines, food & culture journalism",
        "palette": "editorial-cream",
        "fonts": "editorial-luxury",
        "animation": "slide-left",
        "styles": {"hero": 4, "about": 9, "gallery": 3, "blog": 7, "testimonials": 10, "footer": 5},
        "section_theme": "editorial",
        "notes": "Set section_theme 'editorial' on hero, about and blog. Strong typographic hierarchy, generous whitespace, thin rules. Blog feed_type 'latest'.",
    },
    "premium-dark": {
        "when": "luxury brands, premium memberships, high-end portfolios, nightlife",
        "palette": "royal-purple",
        "fonts": "editorial-luxury",
        "animation": "blur",
        "styles": {"hero": 6, "about": 9, "gallery": 5, "vision": 4, "testimonials": 12, "footer": 4},
        "notes": "Dark hero and footer bookends, calm light middle. Accent appears sparingly — one glowing CTA. image_shape 'rounded'.",
    },
    "vibrant-community": {
        "when": "communities, creators, education, nonprofits, family brands",
        "palette": "coral-energy",
        "fonts": "friendly-community",
        "animation": "slide-up",
        "styles": {"hero": 3, "about": 8, "gallery": 3, "team": 6, "testimonials": 6, "subscription": 4, "footer": 2},
        "notes": "Approachable and lively. Circular images (image_shape 'circle') for people, bento gallery for energy. Short friendly copy.",
    },
    "tech-forward": {
        "when": "startups, apps, crypto, gaming-adjacent tech, developer tools",
        "palette": "ocean-teal",
        "fonts": "modern-tech",
        "animation": "slide-left",
        "styles": {"hero": 1, "about": 4, "gallery": 2, "vision": 5, "faq": 2, "subscription": 4, "footer": 3},
        "notes": "Crisp and systematic. Text-only about (style 4) keeps it lean. Feature-grid vision. Benefits + form subscription before footer.",
    },
    "gaming-esports": {
        "when": "active gaming/esports services, streaming, entertainment platforms",
        "palette": "gaming-dark",
        "fonts": "bold-statement",
        "animation": "slide-up",
        "styles": {"hero": 6, "about": 9, "gallery": 7, "video": 3, "ranking": 2, "testimonials": 12, "footer": 4},
        "notes": "High contrast, dark accents, tight image wall. Podium ranking. Keep middle sections light per background rules — energy comes from accent + typography.",
    },
    "nature-wellness": {
        "when": "eco, agriculture, wellness, health, outdoors, NGO field work",
        "palette": "forest-green",
        "fonts": "quiet-minimal",
        "animation": "fade",
        "styles": {"hero": 1, "about": 1, "gallery": 3, "vision": 7, "team": 6, "testimonials": 9, "footer": 2},
        "notes": "Calm and organic. Bento gallery, blob or arch image shapes, soft green tints (bg_alt) between white sections.",
    },
}


def build_font_pairings_block() -> str:
    rows = "\n".join(
        f"  {name:<18}: title font \"{p['title']}\" + body font \"{p['body']}\"   ({p['vibe']})"
        for name, p in FONT_PAIRINGS.items()
    )
    return rows


def build_design_recipes_block() -> str:
    blocks: list[str] = []
    for name, r in DESIGN_RECIPES.items():
        pairing = FONT_PAIRINGS[r["fonts"]]
        styles = ", ".join(f"{k} {v}" for k, v in r["styles"].items())
        lines = [
            f"{name} — use when: {r['when']}",
            f"  palette={r['palette']}  fonts: \"{pairing['body']}\" body + \"{pairing['title']}\" hero title_font  animation={r['animation']}",
            f"  styles: {styles}",
        ]
        if r.get("section_theme"):
            lines.append(f"  section_theme: \"{r['section_theme']}\" on hero/about/blog")
        lines.append(f"  {r['notes']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _validate() -> None:
    """Guard against recipes referencing fonts/palettes/styles that don't exist."""
    for name, p in FONT_PAIRINGS.items():
        assert p["title"] in FONT_OPTIONS, f"{name}: unknown title font {p['title']}"
        assert p["body"] in FONT_OPTIONS, f"{name}: unknown body font {p['body']}"
    for name, r in DESIGN_RECIPES.items():
        assert r["palette"] in CURATED_PALETTES, f"{name}: unknown palette {r['palette']}"
        assert r["fonts"] in FONT_PAIRINGS, f"{name}: unknown pairing {r['fonts']}"
        assert r["animation"] in ANIMATION_STYLES, f"{name}: unknown animation {r['animation']}"
        for section, style in r["styles"].items():
            allowed = {v for v, _l, _d in SECTION_STYLES[section.upper()]}
            assert style in allowed, f"{name}: {section} style {style} not in {sorted(allowed)}"


_validate()
