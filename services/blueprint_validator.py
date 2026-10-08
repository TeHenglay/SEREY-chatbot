# Blueprint post-processor: validates and sanitizes AI-generated sections,
# patches and colors before they are returned to the frontend.
#
# serey-api stores whatever the browser saves (no enum/shape validation, save =
# full replace + media cleanup), so this module is the only server-side guard
# between model output and a user's live page. It REPAIRS or DROPS bad data and
# never raises — a rejected turn would still cost the user a credit.
#
# Canonical section/style knowledge comes from services.section_catalog.

import json
import logging
import os
import re
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

from services.layout_policy import normalize_section_type, normalize_style
from services.section_catalog import GENERATABLE_SECTIONS

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
    - Strips invalid hex values
    - When an explicit bg is present: ensures title/subtitle/body pass 3.5:1
      contrast against it and prevents invisible dark accents on dark backgrounds
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

    # Patch updates and image-backed sections carry partial color dicts. Without
    # an explicit bg we cannot know what the text sits on, so only the hex format
    # is validated — assuming a white bg would flip light-on-image titles to dark.
    if "bg" not in result:
        return result

    bg_lum = _luminance(result["bg"])

    for field in ("title", "subtitle", "body"):
        if field not in result:
            continue
        fg_lum = _luminance(result[field])
        if _contrast(bg_lum, fg_lum) < 3.5:
            result[field] = DARK_TEXT if bg_lum > 0.5 else LIGHT_TEXT

    # Prevent dark accent on dark background
    if "accent" in result and bg_lum < 0.15:
        if _luminance(result["accent"]) < 0.15:
            result["accent"] = FALLBACK_ACCENT

    # Prevent near-white body on near-white bg
    if "body" in result and bg_lum > 0.9 and _luminance(result["body"]) > 0.85:
        result["body"] = DARK_TEXT

    return result


# ---------------------------------------------------------------------------
# Image URL / script scrubbing
# ---------------------------------------------------------------------------

# Hosts whose URLs the AI may emit on its own (Serey media). Anything else must
# already appear in the page context or the user's message (i.e. be echoed, not
# invented). Extend with BUILDER_IMAGE_HOSTS="serey.io,cdn.example.com".
_ALLOWED_IMAGE_HOSTS = tuple(
    h.strip().lower()
    for h in os.getenv("BUILDER_IMAGE_HOSTS", "serey.io").split(",")
    if h.strip()
)

_IMAGE_SCALAR_FIELDS = ("image_url", "image_url_2", "image_url_3", "image_url_4", "logo_url", "bg_image_url")
_IMAGE_ITEM_ARRAYS = ("images", "members", "testimonial_items")
# Third-party embed code is an XSS surface: only keep what the user supplied.
_SCRIPT_FIELDS = ("kit_embed_script", "email_octopus_embed_script")
_SINGLETON_TYPES = ("HERO", "FOOTER")
VALID_PATCH_ACTIONS = ("add_block", "update_block", "delete_block")


def _host_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not host:
        return False
    return any(host == h or host.endswith("." + h) for h in _ALLOWED_IMAGE_HOSTS)


def _clean_image_url(value: Any, known_text: str) -> str:
    """Keep a URL only if it is empty, echoed from known text, or on an allowed host."""
    if not isinstance(value, str) or not value.strip():
        return ""
    url = value.strip()
    if url in known_text or _host_allowed(url):
        return url
    logger.warning("Dropped unverified image URL from AI output: %.120s", url)
    return ""


def sanitize_section_fields(section: dict[str, Any], known_text: str) -> None:
    """In-place scrub of one section dict (or a patch's `updates`)."""
    for field in _IMAGE_SCALAR_FIELDS:
        if field in section:
            section[field] = _clean_image_url(section[field], known_text)
    for array in _IMAGE_ITEM_ARRAYS:
        items = section.get(array)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and "image_url" in item:
                item["image_url"] = _clean_image_url(item["image_url"], known_text)
    for field in _SCRIPT_FIELDS:
        value = section.get(field)
        if isinstance(value, str) and value and value not in known_text:
            logger.warning("Dropped %s not supplied by the user", field)
            section[field] = ""
    if isinstance(section.get("colors"), dict):
        section["colors"] = sanitize_colors(section["colors"])


# ---------------------------------------------------------------------------
# Blueprint (full page) sanitizer
# ---------------------------------------------------------------------------

def _unique_instance_keys(content: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for section in content:
        key = section.get("instance_key")
        if not isinstance(key, str) or not key:
            continue
        candidate, n = key, 1
        while candidate in seen:
            n += 1
            candidate = f"{key}__{n}"
        if candidate != key:
            logger.warning("Renamed duplicate instance_key %r to %r", key, candidate)
            section["instance_key"] = candidate
        seen.add(candidate)


def sanitize_content(content: Any, known_text: str = "") -> list[dict[str, Any]]:
    """Return a cleaned `content` list: known types only, one HERO/FOOTER,
    HERO first / FOOTER last, unique instance keys, scrubbed fields."""
    if not isinstance(content, list):
        return []
    cleaned: list[dict[str, Any]] = []
    singletons: set[str] = set()
    for section in content:
        if not isinstance(section, dict):
            continue
        stype = normalize_section_type(section.get("type"))
        # Types the frontend cannot render (CUSTOM, NEWSLETTER) are dropped there
        # silently anyway — drop them here so layout/uploads match what is shown.
        if stype not in GENERATABLE_SECTIONS:
            logger.warning("Dropped section with unsupported type %r", section.get("type"))
            continue
        if stype in _SINGLETON_TYPES:
            if stype in singletons:
                logger.warning("Dropped duplicate %s section", stype)
                continue
            singletons.add(stype)
        sanitize_section_fields(section, known_text)
        cleaned.append(section)

    # Stable reorder: HERO to the top, FOOTER to the bottom.
    def _rank(s: dict[str, Any]) -> int:
        t = normalize_section_type(s.get("type"))
        return 0 if t == "HERO" else 2 if t == "FOOTER" else 1

    cleaned.sort(key=_rank)
    for missing in (t for t in _SINGLETON_TYPES if t not in singletons):
        logger.warning("Blueprint has no %s section", missing)
    _unique_instance_keys(cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# Patch sanitizer
# ---------------------------------------------------------------------------

def existing_section_types(content: Any) -> set[str] | None:
    """Types present in the page-context content list, or None if unknown."""
    if not isinstance(content, list):
        return None
    return {
        normalize_section_type(s.get("type"))
        for s in content
        if isinstance(s, dict) and s.get("type") is not None
    }


def sanitize_patch(
    patch: dict[str, Any],
    known_types: set[str] | None,
    known_text: str = "",
) -> dict[str, Any] | None:
    """Validate one normalized patch dict. Returns None to drop it.

    `known_types` is mutated as the batch is walked so a later patch can target a
    section added by an earlier one. Pass None when the page layout is unknown
    (prose page_context) — only shape checks run then.
    """
    action = patch.get("action")
    ptype = normalize_section_type(patch.get("type"))
    if action not in VALID_PATCH_ACTIONS:
        logger.warning("Dropped patch with invalid action %r", action)
        return None
    if ptype not in GENERATABLE_SECTIONS:
        logger.warning("Dropped %s patch with unsupported type %r", action, patch.get("type"))
        return None

    if known_types is not None:
        if action == "add_block":
            if ptype in _SINGLETON_TYPES and ptype in known_types:
                logger.warning("Dropped add_block for %s — the page already has one", ptype)
                return None
            known_types.add(ptype)
        elif ptype not in known_types:
            # Previously the derived layout silently created the section while
            # the frontend ignored the patch — the two disagreed.
            logger.warning("Dropped %s for %s — the page has no such section", action, ptype)
            return None

    updates = patch.get("updates")
    if isinstance(updates, dict):
        sanitize_section_fields(updates, known_text)
    patch["type"] = ptype
    return patch


# ---------------------------------------------------------------------------
# Raw AI response helpers (stateless one-shot generator)
# ---------------------------------------------------------------------------

def validate_blueprint(raw: dict | list, known_text: str = "") -> dict:
    """Unwrap {"content": [...]}, {"sections": [...]} or a bare list and clean it."""
    if isinstance(raw, list):
        sections: Any = raw
    elif isinstance(raw, dict):
        sections = raw.get("content") or raw.get("sections") or raw.get("blocks") or []
    else:
        sections = []
    cleaned = sanitize_content(deepcopy(sections), known_text)
    for section in cleaned:
        stype = normalize_section_type(section.get("type"))
        section["type"] = stype
        section["style"], _ = normalize_style(stype, section.get("style"))
    return {"content": cleaned}


def parse_ai_response(raw_text: str) -> dict:
    """Parse the AI's raw text into a cleaned blueprint dict (fences tolerated)."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines() if not l.startswith("```")).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse AI response as JSON: %s\nRaw: %.500s", e, raw_text)
        raise ValueError(f"AI returned invalid JSON: {e}") from e
    return validate_blueprint(parsed)
