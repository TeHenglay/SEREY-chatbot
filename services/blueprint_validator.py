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
from services.section_catalog import CODE_SECTION_KEY, CODE_SECTION_TYPE, GENERATABLE_SECTIONS

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


def is_neutral(hex_color: str | None) -> bool:
    """White, grey or black: no visible hue (light brand tints like #eff6ff
    still count as colour)."""
    h = _parse_hex(hex_color)
    if not h:
        return False
    rgb = [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    return max(rgb) - min(rgb) <= 10


def _mix(hex_color: str, toward: tuple[int, int, int], amount: float) -> str:
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(c + (t - c) * amount):02x}" for c, t in zip(rgb, toward))


def separate_adjacent_backgrounds(content: list[dict[str, Any]], page_owned: frozenset[str] = frozenset()) -> int:
    """No two visible sections next to each other may share a background colour.

    When they do, the second one gets another background already used on the
    page (not its neighbours' colour), else a light tint of the page's accent
    (a lighter shade on dark backgrounds) — never a plain grey — and its text
    colours are re-checked for contrast.
    Sections over a background image and the user's own Custom Code sections
    (`page_owned` keys) are left alone (a neighbour after one changes instead). Run on the
    final section order (after sanitize_content). Returns how many sections
    were changed."""
    visible = [s for s in content if isinstance(s, dict) and not s.get("is_hidden")]

    def bg(s: dict[str, Any]) -> str | None:
        colors = s.get("colors")
        return _parse_hex(colors.get("bg")) if isinstance(colors, dict) else None

    accents = [a for s in visible if isinstance(s.get("colors"), dict) and (a := _parse_hex(s["colors"].get("accent")))]
    accent = max(set(accents), key=accents.count) if accents else None
    accent_rgb = tuple(int(accent[i:i + 2], 16) for i in (1, 3, 5)) if accent and not is_neutral(accent) else None

    palette: list[str] = []
    for s in visible:
        b = bg(s)
        if b and b not in palette:
            palette.append(b)

    changed = 0
    for i in range(1, len(visible)):
        cur, prev = visible[i], visible[i - 1]
        if cur.get("bg_image_url") or prev.get("bg_image_url"):
            continue
        if normalize_section_type(cur.get("type")) == CODE_SECTION_TYPE and _section_key(cur) in page_owned:
            continue
        b, pb = bg(cur), bg(prev)
        if not b or b != pb:
            continue
        nb = bg(visible[i + 1]) if i + 1 < len(visible) else None
        lum = _luminance(b)
        # Another colour of the page with the same lightness (light stays light, dark stays dark)
        choice = next(
            (p for p in palette if p not in (b, nb) and (_luminance(p) > 0.5) == (lum > 0.5)),
            None,
        )
        if choice is None:
            # Light: tint toward the brand accent (toward black only without one,
            # which made white pages alternate with grey). Dark: lighten.
            toward = accent_rgb if lum > 0.5 and accent_rgb else (0, 0, 0) if lum > 0.5 else (255, 255, 255)
            for amount in ((0.1, 0.16, 0.22) if toward == accent_rgb else (0.07, 0.12, 0.18)):
                choice = _mix(b, toward, amount)
                if choice not in (pb, nb):
                    break
        cur["colors"] = sanitize_colors({**cur["colors"], "bg": choice})
        logger.warning("Adjacent sections shared bg %s — changed the second to %s", b, choice)
        changed += 1
    return changed


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
# Custom Code sections (type 11) written by the AI
# ---------------------------------------------------------------------------

CODE_SECTION_HTML_MAX = 50_000
_CODE_FENCE_RE = re.compile(r"^\s*```[\w-]*\s*|\s*```\s*$")

# Clickable-looking HTML. Bob's code may be interactive (a wheel, tabs, an
# accordion) when its own script makes every control do something; controls
# that do nothing are dead ends (a "Book of the Week" pill row looked like a
# filter bar that did nothing) — see dead_controls().
_INTERACTIVE_HTML_RE = re.compile(
    r"<\s*(?:button|a|input|select|textarea|form|nav|label|details|summary)\b"
    r"|\bonclick\s*=|\brole\s*=\s*[\"']?(?:button|tab|link|menuitem)"
    r"|cursor\s*:\s*pointer"
    r"|class\s*=\s*[\"'][^\"']*\b(?:pill|pills|chip|chips|tag|tags|tab|tabs|filter|filters|category|categories|btn|button)\b",
    re.IGNORECASE,
)
# Pills styled inline: the same rounded inline style repeated on 3+ items.
_INLINE_PILL_RE = re.compile(r"""style\s*=\s*["'][^"']*border-radius\s*:\s*(?:\d{2,}px|50%)""", re.IGNORECASE)


def is_interactive_html(html: Any) -> bool:
    if not isinstance(html, str):
        return False
    return bool(_INTERACTIVE_HTML_RE.search(html)) or len(_INLINE_PILL_RE.findall(html)) >= 3


_FORM_RE = re.compile(r"<\s*(?:form|input|select|textarea)\b", re.IGNORECASE)
_LINK_HREF_RE = re.compile(r"""<\s*a\b[^>]*?\bhref\s*=\s*["']?([^"'\s>]*)""", re.IGNORECASE)
_EXTERNAL_SCRIPT_RE = re.compile(r"<\s*script\b[^>]*\bsrc\s*=", re.IGNORECASE)
_SCRIPT_RE = re.compile(r"<\s*script\b[^>]*>(.*?)<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL)
_HANDLER_RE = re.compile(r"addEventListener\s*\(|\.on(?:click|mouseenter|mouseover|keydown|pointerdown)\s*=", re.IGNORECASE)


def dead_controls(html: Any, known_text: str = "") -> str | None:
    """Why the code has controls that lead nowhere, or None. Clickable parts
    are fine when the snippet's own script wires them up (tabs, a wheel, an
    accordion); links only to URLs the user gave."""
    if not isinstance(html, str):
        return None
    if _FORM_RE.search(html):
        return "a form or input that sends nowhere"
    if _EXTERNAL_SCRIPT_RE.search(html):
        return "an external script (write all code inline)"
    for href in _LINK_HREF_RE.findall(html):
        target = href.strip()
        if not target or target.startswith(("#", "javascript:")) or target not in (known_text or ""):
            return "a link that goes nowhere or to a URL the user never gave"
    if is_interactive_html(re.sub(r"<\s*a\b", "<x", html)):
        scripts = " ".join(_SCRIPT_RE.findall(html))
        if not (_HANDLER_RE.search(scripts) or re.search(r"\bon(?:click|mouseenter|mouseover)\s*=", html, re.IGNORECASE)):
            return "buttons, pills, tabs or other clickable-looking parts that no script makes work"
    return None


# "AI look" the code must not have: emoji, gradients (and the transparent-text
# trick that only works with one), and viewport heights — in the auto-height
# iframe a vh/% height measures the frame itself, so the section never grows
# to its content and the bottom is cut off.
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\U0001F1E6-\U0001F1FF"
    "‍️⃣]"
)
_CSS_DECL_END = r"[^;{}\"']*;?"
_GRADIENT_DECL_RE = re.compile(r"[\w-]+\s*:[^;{}\"']*gradient\(" + _CSS_DECL_END, re.IGNORECASE)
_TEXT_CLIP_DECL_RE = re.compile(
    r"(?:-webkit-)?(?:background-clip\s*:\s*text|text-fill-color\s*:\s*transparent)\s*;?"
    r"|(?<![\w-])color\s*:\s*transparent\s*;?",
    re.IGNORECASE,
)
_VIEWPORT_HEIGHT_RE = re.compile(
    r"(?<![\w-])(?:min-|max-)?height\s*:\s*\d+(?:\.\d+)?(?:vh|dvh|svh|lvh)\s*;?", re.IGNORECASE
)
_FIXED_POSITION_RE = re.compile(r"position\s*:\s*fixed", re.IGNORECASE)


def clean_code_html(html: Any) -> str:
    """The model's HTML without markdown fences, emoji, gradients or viewport
    heights, capped at the editor limit."""
    if not isinstance(html, str):
        return ""
    html = _CODE_FENCE_RE.sub("", html.strip())
    html = _EMOJI_RE.sub("", html)
    html = _GRADIENT_DECL_RE.sub("", html)
    html = _TEXT_CLIP_DECL_RE.sub("", html)
    html = _VIEWPORT_HEIGHT_RE.sub("", html)
    html = _FIXED_POSITION_RE.sub("position:relative", html)
    return html[:CODE_SECTION_HTML_MAX]


def code_style_problems(html: Any, known_text: str = "") -> list[str]:
    """Design rules Bob's code broke (for the quality retry); clean_code_html()
    removes most of them anyway, this makes the model fix them properly.
    "AI" on the page is fine when the user's own text mentions it."""
    if not isinstance(html, str):
        return []
    problems = []
    if _EMOJI_RE.search(html):
        problems.append("emoji (use none, not even as icons — draw icons with CSS or inline SVG)")
    if "gradient(" in html.lower():
        problems.append("gradients (use flat colours from the page's palette)")
    if _VIEWPORT_HEIGHT_RE.search(html) or _FIXED_POSITION_RE.search(html):
        problems.append("vh heights or position:fixed (let the content set the height)")
    if _AI_LABEL_RE.search(_TAG_TEXT_RE.sub(" ", html)) and not _AI_LABEL_RE.search(known_text):
        problems.append("an \"AI\" label or badge (never mention AI on the page)")
    return problems


_TAG_TEXT_RE = re.compile(r"<style\b.*?</style>|<[^>]+>", re.IGNORECASE | re.DOTALL)
_AI_LABEL_RE = re.compile(r"\bAI\b|\bA\.I\.|artificial intelligence|\bai[- ](?:powered|generated|driven)\b")


def build_code_section(section: dict[str, Any], known_text: str = "") -> dict[str, Any] | None:
    """A Custom Code section the AI wrote, reduced to the fields the section
    has (html, bg colour, ...). None when it cannot stay: no HTML, or controls
    that lead nowhere (dead_controls)."""
    html = clean_code_html(section.get("html"))
    if not html:
        logger.warning("Dropped Custom Code section without html")
        return None
    reason = dead_controls(html, known_text)
    if reason:
        logger.warning("Dropped Custom Code section with %s", reason)
        return None
    colors = section.get("colors") if isinstance(section.get("colors"), dict) else {}
    bg = _parse_hex(colors.get("bg"))
    built: dict[str, Any] = {
        "type": CODE_SECTION_TYPE,
        "title": "Custom Code",
        "html": html,
        "style": 1,
        "is_hidden": False,
        "colors": {"bg": bg} if bg else {},
        "bg_image_url": "",
        "bg_image_opacity": 0.5,
        "section_height": 0,
        "section_theme": "",
        "text_styles": {},
    }
    key = section.get("instance_key")
    if isinstance(key, str) and key:
        built["instance_key"] = key
    return built


def _bg_of(section: dict[str, Any]) -> str | None:
    colors = section.get("colors")
    return _parse_hex(colors.get("bg")) if isinstance(colors, dict) else None


_THEME_VARS_RE = re.compile(r"<style data-page-theme>.*?</style>", re.DOTALL)


def inject_code_theme_vars(content: list[dict[str, Any]], page_owned: frozenset[str] = frozenset()) -> None:
    """Give each of Bob's Code sections the colours of the background it ended
    up on, as CSS variables at the top of its html: --page-text, --page-muted,
    --page-accent, --page-card and --page-line. Bob cannot know whether his
    section lands on a light or a dark background (themes alternate), so his
    CSS uses these instead of fixed text colours. Run after every colour pass."""
    accents = [a for s in content if (a := _parse_hex((s.get("colors") or {}).get("accent")))]
    accent = max(set(accents), key=accents.count) if accents else "#2563eb"
    for section in content:
        if normalize_section_type(section.get("type")) != CODE_SECTION_TYPE or _section_key(section) in page_owned:
            continue
        html = section.get("html")
        bg = _parse_hex((section.get("colors") or {}).get("bg"))
        if not isinstance(html, str) or not bg:
            continue
        dark = _luminance(bg) <= 0.179
        text = "#f8fafc" if dark else "#0f172a"
        muted = "#cbd5e1" if dark else "#475569"
        card = _mix(bg, (255, 255, 255), 0.08) if dark else "#ffffff"
        line = _mix(bg, (255, 255, 255), 0.22) if dark else _mix(bg, (0, 0, 0), 0.12)
        # The accent must read on this background: lighten it on dark ones.
        acc = accent
        if dark and _contrast(_luminance(acc), _luminance(bg)) < 3:
            acc = _mix(accent, (255, 255, 255), 0.55)
        vars_css = (f"<style data-page-theme>:root{{--page-bg:{bg};--page-text:{text};--page-muted:{muted};"
                    f"--page-accent:{acc};--page-card:{card};--page-line:{line};color:{text}}}</style>")
        section["html"] = vars_css + _THEME_VARS_RE.sub("", html)


def apply_theme_to_code_sections(content: list[dict[str, Any]], page_owned: frozenset[str] = frozenset()) -> None:
    """Bob's Code sections take a background from the page's own palette: keep
    one that another section uses, else take the nearest section's colour
    (separate_adjacent_backgrounds() then swaps it for another page colour when
    it touches that section). The user's own Code sections (`page_owned` keys)
    are left alone."""
    palette = {
        b for s in content
        if normalize_section_type(s.get("type")) != CODE_SECTION_TYPE and (b := _bg_of(s))
    }
    for i, section in enumerate(content):
        if normalize_section_type(section.get("type")) != CODE_SECTION_TYPE or _section_key(section) in page_owned:
            continue
        if _bg_of(section) in palette:
            continue
        nearby = [*content[i - 1::-1], *content[i + 1:]] if i else content[1:]
        fallback = next((b for s in nearby if (b := _bg_of(s)) in palette), None)
        if fallback:
            logger.warning("Code section bg %r is not a page colour — using %s", _bg_of(section), fallback)
            section["colors"] = {**(section.get("colors") or {}), "bg": fallback}


# ---------------------------------------------------------------------------
# Blueprint (full page) sanitizer
# ---------------------------------------------------------------------------

def _unique_instance_keys(content: list[dict[str, Any]]) -> None:
    # Custom Code sections claim their keys first (the user's own one keeps its
    # key); any other section using it is renamed.
    is_code = [normalize_section_type(s.get("type")) == CODE_SECTION_TYPE for s in content]
    ordered = [s for s, c in zip(content, is_code) if c] + [s for s, c in zip(content, is_code) if not c]
    seen: set[str] = set()
    for section in ordered:
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


def _section_key(section: dict[str, Any]) -> str:
    """The builder key of a section: its instance_key, else the bare name
    ("code" for the Custom Code section, the lowercase type otherwise)."""
    key = section.get("instance_key")
    if isinstance(key, str) and key:
        return key
    stype = normalize_section_type(section.get("type"))
    return CODE_SECTION_KEY if stype == CODE_SECTION_TYPE else stype.lower()


def page_code_sections(page_content: Any) -> list[dict[str, Any]]:
    """The Custom Code sections (type 11) of the current page state, in order."""
    if not isinstance(page_content, list):
        return []
    return [
        s for s in page_content
        if isinstance(s, dict) and normalize_section_type(s.get("type")) == CODE_SECTION_TYPE
    ]


def _restore_code_sections(
    cleaned: list[dict[str, Any]],
    placed: set[str],
    page_content: list[Any],
) -> None:
    """Put back every Custom Code section of the page the model did not place:
    right after the nearest section before it on the page that is still there,
    or at the top of the middle sections when there is none."""
    anchor: str | None = None
    for section in page_content:
        if not isinstance(section, dict):
            continue
        key = _section_key(section)
        keys = [_section_key(s) for s in cleaned]
        if normalize_section_type(section.get("type")) == CODE_SECTION_TYPE and key not in placed:
            cleaned.insert(keys.index(anchor) + 1 if anchor in keys else 0, _code_section_copy(section))
            placed.add(key)
            logger.info("Kept Custom Code section %r the model left out", key)
            anchor = key
        elif key in keys:
            anchor = key


def _code_section_copy(section: dict[str, Any]) -> dict[str, Any]:
    copy = deepcopy(section)
    copy["type"] = CODE_SECTION_TYPE
    return copy


def sanitize_content(
    content: Any,
    known_text: str = "",
    page_content: Any = None,
) -> list[dict[str, Any]]:
    """Return a cleaned `content` list: known types only, one HERO/FOOTER,
    HERO first / FOOTER last, unique instance keys, scrubbed fields.

    Custom Code sections (type 11): a model entry with `html` is a new section
    Bob wrote (build_code_section). The page's own ones (from `page_content`,
    the current page state) are never overwritten here and come back
    unchanged; a model entry without `html` only sets where one of them goes,
    the rest keep their place after the section they followed."""
    if not isinstance(content, list):
        return []
    code_sections = {_section_key(s): s for s in page_code_sections(page_content)}
    placed: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    singletons: set[str] = set()
    for section in content:
        if not isinstance(section, dict):
            continue
        stype = normalize_section_type(section.get("type"))
        if stype == CODE_SECTION_TYPE:
            key = _section_key(section)
            if section.get("html"):
                built = build_code_section(section, known_text)
                if built is not None:
                    if key in code_sections:
                        # Never overwrite the user's own section: this is a new one.
                        built.pop("instance_key", None)
                    cleaned.append(built)
            elif key in code_sections and key not in placed:
                cleaned.append(_code_section_copy(code_sections[key]))
                placed.add(key)
            else:
                logger.warning("Dropped empty Custom Code section %r", key)
            continue
        # Types the frontend cannot render (NEWSLETTER) are dropped there
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
    if code_sections:
        _restore_code_sections(cleaned, placed, page_content)

    # Stable reorder: HERO to the top, FOOTER to the bottom.
    def _rank(s: dict[str, Any]) -> int:
        t = normalize_section_type(s.get("type"))
        return 0 if t == "HERO" else 2 if t == "FOOTER" else 1

    cleaned.sort(key=_rank)
    for missing in (t for t in _SINGLETON_TYPES if t not in singletons):
        logger.warning("Blueprint has no %s section", missing)
    _unique_instance_keys(cleaned)
    _key_new_code_sections(cleaned)
    return cleaned


def page_code_keys(page_content: Any) -> frozenset[str]:
    """Keys of the user's own Code sections on the current page."""
    return frozenset(_section_key(s) for s in page_code_sections(page_content))


def _key_new_code_sections(content: list[dict[str, Any]]) -> None:
    """Give every Code section an instance key ("code", then "code__2", ...)
    so a new one never takes the key of one already on the page."""
    used = {
        _section_key(s) for s in content
        if s.get("instance_key") or normalize_section_type(s.get("type")) != CODE_SECTION_TYPE
    }
    n = 1
    for section in content:
        if normalize_section_type(section.get("type")) != CODE_SECTION_TYPE or section.get("instance_key"):
            continue
        while (key := CODE_SECTION_KEY if n == 1 else f"{CODE_SECTION_KEY}__{n}") in used:
            n += 1
        section["instance_key"] = key
        used.add(key)


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
    if ptype == CODE_SECTION_TYPE:
        return _sanitize_code_patch(patch, known_types, known_text)
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


def _sanitize_code_patch(
    patch: dict[str, Any],
    known_types: set[str] | None,
    known_text: str = "",
) -> dict[str, Any] | None:
    """A patch on a Custom Code section: add_block needs html (checked like a
    blueprint one); update_block may only change html and the bg colour;
    delete_block passes."""
    action = patch["action"]
    patch["type"] = CODE_SECTION_TYPE
    if action != "add_block" and known_types is not None and CODE_SECTION_TYPE not in known_types:
        logger.warning("Dropped %s for a Custom Code section — the page has none", action)
        return None
    if action == "delete_block":
        patch["updates"] = {}
        return patch
    updates = patch.get("updates") if isinstance(patch.get("updates"), dict) else {}
    if action == "add_block":
        built = build_code_section(updates, known_text)
        if built is None:
            return None
        built.pop("type")
        patch["updates"] = built
        if known_types is not None:
            known_types.add(CODE_SECTION_TYPE)
        return patch
    kept: dict[str, Any] = {}
    if "html" in updates:
        html = clean_code_html(updates["html"])
        if not html or dead_controls(html, known_text):
            logger.warning("Dropped Custom Code html update (empty or with controls that lead nowhere)")
        else:
            kept["html"] = html
    bg = _parse_hex((updates.get("colors") or {}).get("bg")) if isinstance(updates.get("colors"), dict) else None
    if bg:
        kept["colors"] = {"bg": bg}
    if not kept:
        logger.warning("Dropped Custom Code update_block with nothing it may change")
        return None
    patch["updates"] = kept
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
        section["style"], _ = normalize_style(stype, section.get("style"), section.get("section_subtype"))
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
