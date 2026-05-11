# Blueprint post-processor: validates and sanitizes AI-generated section colors
# and structure before returning to the frontend.

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def _parse_hex(value: str | None) -> str | None:
    """Normalize a hex color string to #rrggbb. Returns None if invalid."""
    if not value or not isinstance(value, str):
        return None
    raw = value.strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{3}", raw):
        raw = "".join(c * 2 for c in raw)
    if re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        return f"#{raw.lower()}"
    return None


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    def linearize(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _contrast(lum_a: float, lum_b: float) -> float:
    lo, hi = min(lum_a, lum_b), max(lum_a, lum_b)
    return (hi + 0.05) / (lo + 0.05)


DARK_TEXT  = "#0f172a"
LIGHT_TEXT = "#f0f4ff"
FALLBACK_ACCENT = "#3b82f6"


def sanitize_colors(colors: dict | None) -> dict | None:
    """
    Validate and fix a section's colors dict:
    - Strips invalid hex values (replaces with section defaults or safe fallbacks)
    - Ensures title/subtitle/body pass 3.5:1 contrast against background
    - Prevents invisible dark accents on dark backgrounds
    """
    if not colors or not isinstance(colors, dict):
        return colors

    result = {}
    for k, v in colors.items():
        parsed = _parse_hex(v)
        if parsed:
            result[k] = parsed
        else:
            logger.debug("Dropped invalid color %r=%r from section", k, v)

    bg = result.get("bg", "#ffffff")
    bg_lum = _luminance(bg)

    for field in ("title", "subtitle", "body"):
        if field not in result:
            continue
        fg_lum = _luminance(result[field])
        if _contrast(bg_lum, fg_lum) < 3.5:
            result[field] = DARK_TEXT if bg_lum > 0.5 else LIGHT_TEXT

    # Prevent dark accent on dark background
    if "accent" in result and bg_lum < 0.15:
        accent_lum = _luminance(result["accent"])
        if accent_lum < 0.15:
            result["accent"] = FALLBACK_ACCENT

    # Prevent near-white body on near-white bg
    if "body" in result and bg_lum > 0.9 and _luminance(result["body"]) > 0.85:
        result["body"] = DARK_TEXT

    return result


# ---------------------------------------------------------------------------
# Blueprint post-processor
# ---------------------------------------------------------------------------

VALID_TYPES = {
    "HERO", "ABOUT", "GALLERY", "FOOTER",
    "VIDEO", "VISION", "BLOG", "TEAM",
    "FAQ", "TESTIMONIALS", "CUSTOM", "RANKING",
}

# Valid style numbers per section type
VALID_STYLES: dict[str, set[int]] = {
    "HERO":         {1, 2, 3, 4, 5, 6},
    "ABOUT":        {1, 2, 3, 4, 5, 6, 7, 8},
    "GALLERY":      {1, 2, 3, 4, 5, 7, 9, 12, 13, 14, 16},
    "VIDEO":        {1, 2, 3, 4, 5},
    "VISION":       {1, 2, 3, 4, 5, 6},
    "BLOG":         {1, 2, 3, 4, 5, 6},
    "TEAM":         {1, 2, 4, 5, 6, 7},
    "FAQ":          {1, 2, 3, 4, 5, 6},
    "TESTIMONIALS": {1, 2, 3, 4, 5, 6, 7},
    "CUSTOM":       {1, 2, 3, 4, 5, 6},
    "RANKING":      {1, 2, 3, 4},
    "FOOTER":       {1, 2, 3},
}

# Default fallback style per section (not style 1 to encourage variety)
DEFAULT_STYLE: dict[str, int] = {
    "HERO": 3, "ABOUT": 7, "GALLERY": 2, "VIDEO": 4,
    "VISION": 5, "BLOG": 3, "TEAM": 7, "FAQ": 5,
    "TESTIMONIALS": 7, "CUSTOM": 4, "RANKING": 3, "FOOTER": 1,
}


def validate_blueprint(raw: dict | list) -> dict:
    """
    Validate and sanitize a blueprint dict from the AI.

    Handles both:
      - {"content": [...sections...]}   ← preferred wrapper format
      - [...sections...]                ← bare list
      - {"sections": [...]}             ← alternate key the AI sometimes uses

    Returns: {"content": [validated sections]}
    """
    # Unwrap various formats the AI might return
    if isinstance(raw, list):
        sections = raw
    elif isinstance(raw, dict):
        sections = raw.get("content") or raw.get("sections") or raw.get("blocks") or []
        if not isinstance(sections, list):
            sections = []
    else:
        sections = []

    cleaned = []
    seen_types = set()

    for section in sections:
        if not isinstance(section, dict):
            continue

        # Normalize type
        stype = str(section.get("type", "")).upper().strip()
        if stype not in VALID_TYPES:
            logger.warning("Dropping unknown section type: %r", stype)
            continue

        # No duplicate sections (AI sometimes repeats HERO or FOOTER)
        if stype in seen_types and stype not in {"CUSTOM"}:
            logger.warning("Dropping duplicate section: %r", stype)
            continue
        seen_types.add(stype)

        # Validate style
        valid = VALID_STYLES.get(stype, {1})
        style = section.get("style")
        try:
            style = int(style)
        except (TypeError, ValueError):
            style = None
        if style not in valid:
            style = DEFAULT_STYLE.get(stype, 1)
            logger.debug("Corrected invalid style for %s → %d", stype, style)

        # Sanitize colors
        colors = sanitize_colors(section.get("colors"))

        out = {k: v for k, v in section.items() if k not in ("type", "style", "colors")}
        out["type"] = stype
        out["style"] = style
        if colors:
            out["colors"] = colors

        cleaned.append(out)

    return {"content": cleaned}


def parse_ai_response(raw_text: str) -> dict:
    """
    Parse the AI's raw text response into a validated blueprint dict.
    Handles JSON wrapped in markdown code fences or bare JSON.
    """
    text = raw_text.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse AI response as JSON: %s\nRaw: %.500s", e, raw_text)
        raise ValueError(f"AI returned invalid JSON: {e}") from e

    return validate_blueprint(parsed)
