# POST /api/builder/chat — Conversational AI page builder for Serey V2 landing pages.
# The user describes or iterates on a page in plain language.
# The AI responds with a text reply AND an updated PageBlueprint (or null if not applicable).
# The blueprint matches the V2 API contract: { community_id, content: [...sections] }

import asyncio
from copy import deepcopy
from fastapi import APIRouter, HTTPException, Header, Depends
from services.security import require_serey_origin
from schemas.chat import (
    BuilderChatRequest, ChatRequest, BuilderChatResponse, BuilderUsage, GeneratedImage, StyleSelection,
    UploadNeeded,
)
from schemas.blueprint import PageBlueprint, PatchCommand
from services import grok
from services import image_gen
from services import section_catalog as catalog
from services.layout_policy import (
    collect_rendered_upload_slots,
    compare_with_backend_map,
    derive_uploads_needed,
    get_rendered_fields,
    normalize_section_type,
    normalize_style,
    parse_frontend_style_map,
)
from services.blueprint_validator import (
    apply_theme_to_code_sections,
    inject_code_theme_vars,
    is_neutral,
    code_style_problems,
    existing_section_types,
    dead_controls,
    page_code_keys,
    sanitize_content,
    sanitize_patch,
    separate_adjacent_backgrounds,
)
from services.memory import append_session_turn, get_session_history_prompt
from services.community_facts import get_community_facts
import json
import logging
import os
import random
import re
import threading
import time
from typing import Any
from urllib.parse import urlparse

router = APIRouter()
logger = logging.getLogger(__name__)

_CHAT_API_KEY = os.getenv("CHAT_API_KEY", "")

# serey-api's builder proxy aborts after 120s (BUILDER_TIMEOUT_MS); anything we
# generate after that is billed by xAI and thrown away. Keep a margin under it.
_BUILDER_TIME_BUDGET_S = float(os.getenv("BUILDER_TIME_BUDGET_S", "110"))
# A re-generation is only attempted if at least this much budget is left.
_MIN_RETRY_BUDGET_S = 30.0
# A quality re-generation of a full page takes ~30-40s, so it needs more room.
_MIN_QUALITY_RETRY_BUDGET_S = 50.0
# Full page builds: a stronger copywriter (grok-4.7), thinking on "low", and
# more creative freedom. Measured (2026-10-15, 8 builds each): grok-4.7 "low"
# ~40s with clearly better copy than grok-4.3 "medium" (~33s). Keep an effort
# set for grok-4.7: on its default it thinks ~175s, past serey-api's 120s limit.
# Edits stay on grok.BUILDER_MODEL (grok-4.3) with its default effort.
BUILDER_FULL_MODEL = os.getenv("BUILDER_FULL_MODEL", "grok-4.7").strip()
# Longest wait for the full-build model before falling back to grok-4.3
# (~15-20s), and the budget that fallback needs.
_FULL_BUILD_CALL_TIMEOUT_S = float(os.getenv("BUILDER_FULL_CALL_TIMEOUT_S", "65"))
_MIN_FALLBACK_BUDGET_S = 30.0
_FULL_BUILD_REASONING_EFFORT = os.getenv("BUILDER_FULL_REASONING_EFFORT", "low").strip().lower()
_FULL_BUILD_TEMPERATURE = float(os.getenv("BUILDER_FULL_TEMPERATURE", "0.9"))
_RETRY_NOTE_INVALID_JSON = (
    "\n\nIMPORTANT: your previous answer was not valid JSON. Reply with ONE valid JSON "
    "object only — no prose before or after it, no markdown fences."
)
_RETRY_NOTE_TRUNCATED = (
    "\n\nIMPORTANT: your previous answer was cut off because it was too long. Reply with "
    "ONE valid JSON object and keep it shorter: concise copy, no optional fields."
)

# ---------------------------------------------------------------------------
# Per-session previous page state — powers partial undo ("undo the color
# change", "put the old title back"). The frontend handles full reverts
# locally from its own history; here we keep the page_context from the
# previous turn so the AI can see the old values and restore them via patches.
# In-process store (same lifetime model as the short-term session memory).
# ---------------------------------------------------------------------------

# Broad on purpose: this only gates injecting PREVIOUS PAGE STATE into the
# prompt (a few extra tokens when slightly off), so it must catch every way
# people say "give me the old one" — including "i want the old color theme back".
_UNDO_INTENT_RE = re.compile(
    r"\b(revert|undo|go back|back to|previous|restore|original|before|as it was|bring back|old|earlier|back|again)\b",
    re.IGNORECASE,
)

# Color-only request detection: when the user asks purely about colors/theme,
# any "style" the model sneaks into update_block patches is stripped so a
# color change can never silently rearrange the layout.
_COLOR_INTENT_RE = re.compile(
    r"\b(colou?r|theme|palette|background|bg|darker|lighter|dark mode|light mode|warmer|cooler)\b",
    re.IGNORECASE,
)
_LAYOUT_INTENT_RE = re.compile(
    r"\b(layout|style|design|look|redesign|rearrange|reorder|split|magazine|cinematic|centered|template|section)\b",
    re.IGNORECASE,
)


def _is_color_only_request(message: str) -> bool:
    if not message:
        return False
    return bool(_COLOR_INTENT_RE.search(message)) and not _LAYOUT_INTENT_RE.search(message)
_KHMER_UNDO_TERMS = ("ដូចមុន", "ត្រឡប់", "ត្រលប់", "មិនយក")
_KHMER_CHAR_RE = re.compile(r"[ក-៿]")

# Explicit restore intent — used to GATE deterministic reverts (unlike the
# broad _UNDO_INTENT_RE above, which only gates prompt injection). Matches
# "undo"/"revert"/"restore", "old … back" in either word order, and
# "like (it was) before" — but NOT "make it darker again" or "back to white".
_EXPLICIT_RESTORE_RE = re.compile(
    r"\b(undo|revert|restore)\b"
    r"|\b(old|previous|earlier|original)\b.{0,40}\bback\b"
    r"|\bback\b.{0,40}\b(old|previous|earlier|original|before)\b"
    r"|\blike (it was )?before\b",
    re.IGNORECASE,
)

# A restore request that names a specific target is a PARTIAL undo — it must
# go to the model with PREVIOUS PAGE STATE, never to the whole-page snapshot
# revert ("undo the color change on the hero only", "restore my old logo").
_PARTIAL_QUALIFIER_RE = re.compile(
    r"\b(only|just|except|section|hero|footer|gallery|galleries|team|about|faq|testimonial(s)?"
    r"|vision|video|blog|ranking|subscription|newsletter|notes|podcast|custom|map|countdown"
    r"|logo|title|subtitle|heading|button|menu|font|image|photo|picture|mockup|screenshot)\b",
    re.IGNORECASE,
)
_PREV_CONTEXT_TTL_SECS = 24 * 3600
_PREV_CONTEXT_MAX_SESSIONS = 500
_prev_page_context: dict[str, tuple[float, str]] = {}


def _has_undo_intent(message: str) -> bool:
    if not message:
        return False
    return bool(_UNDO_INTENT_RE.search(message)) or any(t in message for t in _KHMER_UNDO_TERMS)


# Full-undo detection: the user wants the WHOLE last change rolled back
# ("undo that", "put it back how it was") rather than one specific value
# ("undo the color change" → partial, handled by the model with PREVIOUS
# PAGE STATE). Full undos are answered deterministically with revert=True —
# no model call — and the frontend restores its own local snapshot, which is
# the most complete record of the previous page.
_FULL_UNDO_RE = re.compile(
    r"\b(undo (that|it|this|everything)|revert (that|it|this|everything)"
    r"|put (it|that|them|everything) back"
    r"|(back|make it) (like|how|the way) it was|as it was before|as it was\b"
    r"|go back to (how|the way) it was|restore everything)\b",
    re.IGNORECASE,
)
_KHMER_FULL_UNDO_TERMS = ("ត្រឡប់ក្រោយ", "ត្រលប់ក្រោយ", "មិនយកការផ្លាស់ប្តូរ")


def _is_full_undo(message: str) -> bool:
    if not message:
        return False
    # A named target ("… on the hero only", "restore my old logo") means a
    # PARTIAL undo — hand it to the model with PREVIOUS PAGE STATE instead.
    if _PARTIAL_QUALIFIER_RE.search(message):
        return False
    if _FULL_UNDO_RE.search(message) or any(t in message for t in _KHMER_FULL_UNDO_TERMS):
        return True
    # Bare Khmer "like before" (ដូចមុន) counts as a full undo only when the
    # whole message is short — inside a longer sentence it usually qualifies
    # one specific change ("change the title color back like before").
    return "ដូចមុន" in message and len(message.strip()) <= 25


# ---------------------------------------------------------------------------
# Vision pre-analysis — the chat model only ever sees image URLs, not pixels.
# When the user asks about images ("what's in the photo", "name the products
# based on the images"), we run the uploaded image URLs through the vision
# model first and inject what they actually show into the prompt.
# ---------------------------------------------------------------------------

_IMAGE_WORD_RE = re.compile(
    r"\b(image|images|img|photo|photos|picture|pictures|pic|pics|logo|thumbnail|gallery"
    # Naming/describing a product or item is inherently grounded in its photo —
    # look at the uploaded product images so the AI names them from the pixels,
    # never from imagination (rule 16 forbids guessing product names).
    r"|product|products|item|items|រូបភាព|រូប)\b",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s\"'<>\)\]]+", re.IGNORECASE)
# URLs that belong to IMAGE fields in the page context ('image_url: "…"',
# 'logo_url: "…"', 'bg_image_url: "…"') — button_url / privacy_url links
# must never reach the vision model: one non-image URL can fail the whole
# vision call, and non-images waste the image cap.
_IMAGE_FIELD_URL_RE = re.compile(
    r"\b(?:image_url(?:_2)?|logo_url|bg_image_url)\"?\s*[:=]\s*\"?(https?://[^\s\"'<>\)\]]+)",
    re.IGNORECASE,
)
_NON_IMAGE_HOST_RE = re.compile(
    r"(youtube\.com|youtu\.be|facebook\.com|instagram\.com|t\.me|tiktok\.com|twitter\.com|x\.com|vimeo\.com)",
    re.IGNORECASE,
)
_MAX_VISION_IMAGES = 6

# Freshly-uploaded images arrive in the user's MESSAGE (guided onboarding intake:
# "[image: <url>]" product markers, "Banner images:"/"Additional images:"/"Logo:"
# URLs), not in page_context. Pull those so vision can see what was uploaded.
_BRACKET_IMAGE_RE = re.compile(
    r"\[image:\s*(https?://[^\s\"'<>\)\]]+?)\s*\]", re.IGNORECASE
)
_IMAGE_EXT_RE = re.compile(
    r"\.(?:jpg|jpeg|png|gif|webp|avif|bmp|svg)(?:\?[^\s\"'<>\)\]]*)?$", re.IGNORECASE
)
_USER_UPLOAD_HOST = "upload.serey.io"


def _extract_message_image_urls(message: str | None) -> list[str]:
    if not message:
        return []
    urls: list[str] = []

    def _add(url: str) -> None:
        url = url.rstrip(".,;")
        if url and url not in urls and not _NON_IMAGE_HOST_RE.search(url):
            urls.append(url)

    for url in _BRACKET_IMAGE_RE.findall(message):
        _add(url)
    for url in _URL_RE.findall(message):
        stripped = url.rstrip(".,;")
        if _IMAGE_EXT_RE.search(stripped) or _USER_UPLOAD_HOST in stripped:
            _add(url)
    return urls


def _extract_image_urls(page_context: str | None) -> list[str]:
    if not page_context:
        return []
    candidates = _IMAGE_FIELD_URL_RE.findall(page_context)
    if not candidates:
        # Context format without field labels — fall back to every URL.
        candidates = _URL_RE.findall(page_context)
    urls: list[str] = []
    for url in candidates:
        url = url.rstrip(".,;")
        if _NON_IMAGE_HOST_RE.search(url) or url in urls:
            continue
        urls.append(url)
        if len(urls) >= _MAX_VISION_IMAGES:
            break
    return urls


async def _vision_context(message: str, page_context: str | None) -> tuple[str, bool]:
    """Returns a prompt block describing what the page's images actually show,
    or '' when the message isn't about images / there are no image URLs.

    The second value says whether the vision model was actually called — it is a
    second model call, so serey-api charges an extra credit for it.
    """
    msg_urls = _extract_message_image_urls(message)
    # Run vision when the user is talking about images OR just uploaded some in
    # the message (onboarding intake) — the freshly-uploaded photos are the ones
    # the copy must match, so they take priority over page_context images.
    if not msg_urls and (not message or not _IMAGE_WORD_RE.search(message)):
        return "", False
    urls = list(msg_urls)
    for url in _extract_image_urls(page_context):
        if url not in urls:
            urls.append(url)
    urls = urls[:_MAX_VISION_IMAGES]
    if not urls:
        return "", False
    numbered = "\n".join(f"Image {i}: {u}" for i, u in enumerate(urls, start=1))
    vision_prompt = (
        "For each image, reply with exactly one line in the form "
        "'Image N: <what it shows — the main subject/product, with brand or type if clearly visible>'. "
        "Be factual and specific; do not guess brands you cannot read.\n" + numbered
    )
    try:
        raw = await asyncio.to_thread(grok.generate_vision, vision_prompt, urls, None)
    except Exception as e:
        logger.warning("Vision pre-analysis failed (%s) — continuing without it", str(e))
        # Not charged: a failed call gave the answer nothing to work with.
        return "", False
    return (
        "\n== WHAT THE PAGE'S IMAGES ACTUALLY SHOW (vision analysis — trust this, "
        "match each Image N to its URL in the page state) ==\n"
        f"{numbered}\n{raw.strip()}\n"
    ), True


def _get_prev_page_context(session_id: str) -> str | None:
    entry = _prev_page_context.get(session_id)
    if not entry:
        return None
    ts, ctx = entry
    if time.time() - ts > _PREV_CONTEXT_TTL_SECS:
        _prev_page_context.pop(session_id, None)
        return None
    return ctx


def _store_prev_page_context(session_id: str, page_context: str | None) -> None:
    if not page_context:
        return
    if len(_prev_page_context) >= _PREV_CONTEXT_MAX_SESSIONS:
        oldest = min(_prev_page_context, key=lambda k: _prev_page_context[k][0])
        _prev_page_context.pop(oldest, None)
    _prev_page_context[session_id] = (time.time(), page_context)


# Tracks whether the last page-changing turn was a colors-only edit. When it
# was, a "give me the old colors back" request equals undoing that whole turn —
# answered deterministically with revert=True (frontend snapshot restore covers
# every section) instead of trusting the model to repaint each section.
_last_change_color_only: dict[str, tuple[float, bool]] = {}


def _set_last_change_color_only(session_id: str, color_only: bool) -> None:
    if len(_last_change_color_only) >= _PREV_CONTEXT_MAX_SESSIONS:
        oldest = min(_last_change_color_only, key=lambda k: _last_change_color_only[k][0])
        _last_change_color_only.pop(oldest, None)
    _last_change_color_only[session_id] = (time.time(), color_only)


# ---------------------------------------------------------------------------
# Reply language — Bob speaks Dutch to Dutch users (Netherlands IP, or the
# site language set to 'nl') until they ask for English. An explicit switch is
# remembered per session here rather than trusted to the 10-turn history window.
# Only Bob's chat reply follows this; page copy follows the user's own input.
# ---------------------------------------------------------------------------

_DUTCH_COUNTRY_CODES = {"NL"}
# A bare "in English" is NOT a switch: "write my about section in English" is about
# page copy, not about how Bob talks.
_TO_ENGLISH_RE = re.compile(
    r"\b(speak|talk|reply|respond|answer|chat|switch|continue|spreek|praat|antwoord)\b[^.?!]{0,30}\b(english|engels)\b"
    r"|\b(english|engels)\b[^.?!]{0,15}\b(please|pls|plz|graag|alsjeblieft|aub)\b"
    r"|^\s*(english|engels)\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_TO_DUTCH_RE = re.compile(
    r"\b(speak|talk|reply|respond|answer|chat|switch|continue|spreek|praat|antwoord)\b[^.?!]{0,30}\b(dutch|nederlands)\b"
    r"|\b(dutch|nederlands)\b[^.?!]{0,15}\b(please|pls|plz|graag|alsjeblieft|aub)\b"
    r"|^\s*(dutch|nederlands)\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_language_override: dict[str, tuple[float, str]] = {}

# Keep this deliberately conservative: these are common function words that
# distinguish ordinary Dutch/English builder requests, not page-content terms
# such as "site", "color", or "image" that occur in both languages.
_DUTCH_MESSAGE_WORDS = {
    "als", "ben", "bij", "de", "een", "en", "het", "hoe", "in", "is",
    "je", "kun", "maar", "met", "naar", "niet", "ook", "op", "van",
    "verander", "veranderen", "voor", "waar", "wat", "wil", "wilt",
    "zijn", "zo", "zonder",
}
_ENGLISH_MESSAGE_WORDS = {
    "a", "an", "and", "are", "change", "for", "how", "i", "in", "is",
    "make", "my", "of", "on", "please", "the", "to", "want", "what",
    "with", "without", "you",
}


def _requested_language(message: str) -> str | None:
    """'en' / 'nl' when the message explicitly asks Bob to switch language."""
    if not message:
        return None
    wants_en = bool(_TO_ENGLISH_RE.search(message))
    wants_nl = bool(_TO_DUTCH_RE.search(message))
    if wants_en == wants_nl:  # neither, or ambiguous ("translate English to Dutch")
        return None
    return "en" if wants_en else "nl"


def _detected_message_language(message: str) -> str | None:
    """Detect a clear Dutch/English request without external language services."""
    words = set(re.findall(r"[a-zA-ZÀ-ÿ]+", (message or "").lower()))
    dutch_score = len(words & _DUTCH_MESSAGE_WORDS)
    english_score = len(words & _ENGLISH_MESSAGE_WORDS)
    if dutch_score >= 2 and dutch_score > english_score:
        return "nl"
    if english_score >= 2 and english_score > dutch_score:
        return "en"
    return None


# Site languages that pin Bob's reply language. Any other selector value
# (kh, ru, es, …) leaves the model replying in the language the user types.
_SELECTOR_LANGUAGES = {"nl": "nl", "en": "en"}
_last_site_language: dict[str, str] = {}


def _remember_session_value(store: dict, session_id: str, value) -> None:
    if len(store) >= _PREV_CONTEXT_MAX_SESSIONS and session_id not in store:
        oldest = min(store, key=lambda k: store[k][0])
        store.pop(oldest, None)
    store[session_id] = (time.time(), value)


def _resolve_reply_language(request: ChatRequest) -> str | None:
    """Which language Bob replies in; None = follow the language the user types.

    The site's language selector is the source of truth, so switching it to EN
    or NL switches Bob immediately. Order:
      1. an explicit request typed in this message ("speak English")
      2. a typed request earlier this session — unless the selector changed
         since, because the newer selector switch wins
      3. the selector (site_language): nl → Dutch, en → English
      4. no selector value sent (older clients): Dutch for a Netherlands IP
    """
    session_id = request.session_id
    site = (request.site_language or "").strip().lower()
    previous_site = _last_site_language.get(session_id, (0, None))[1]
    if site:
        if previous_site is not None and site != previous_site:
            _language_override.pop(session_id, None)
        _remember_session_value(_last_site_language, session_id, site)

    requested = _requested_language(request.message)
    if requested:
        _remember_session_value(_language_override, session_id, requested)
        return requested
    detected = _detected_message_language(request.message)
    if detected:
        return detected
    entry = _language_override.get(session_id)
    if entry and time.time() - entry[0] <= _PREV_CONTEXT_TTL_SECS:
        return entry[1]
    if site:
        return _SELECTOR_LANGUAGES.get(site)
    if (request.country_code or "").strip().upper() in _DUTCH_COUNTRY_CODES:
        return "nl"
    return None


def _reply_language_directive(lang: str | None) -> str:
    if lang == "nl":
        # A bare "reply in Dutch" gives word-for-word calques of English sentence
        # structure — grammatical but foreign-sounding. Naming the audience and
        # forbidding mirrored structure fixed the same problem in routes/summarize.py.
        return (
            "REPLY LANGUAGE: Dutch (Nederlands). Write the \"reply\" text in Dutch, whatever "
            "language the user types in, unless they explicitly ask for another language.\n"
            "Write it the way a native Dutch speaker would chat with a Dutch customer — not a "
            "translation of an English sentence. Use natural Dutch word order and idiom and "
            "re-express each idea instead of mirroring English structure. Tone: informal 'je/jij' "
            "(never 'u'), warm but down-to-earth and to the point, short sentences. No over-the-top "
            "enthusiasm (no 'Geweldig!' / 'Fantastisch!' openers) and no anglicisms where a common "
            "Dutch word exists — but keep web terms Dutch people actually use (website, homepage, "
            "footer, layout, upload). Example of the register: \"Ik heb een FAQ toegevoegd met de "
            "vragen die klanten het vaakst stellen. Wil je er nog een paar bij?\"\n"
            "This applies ONLY to your chat reply — page copy (titles, descriptions, items) still "
            "follows the language the user writes their business details in.\n\n"
        )
    if lang == "en":
        return (
            "REPLY LANGUAGE: English — the user chose English. Write the \"reply\" text in English, "
            "whatever language they type in. Page copy still follows the language of their "
            "business details.\n\n"
        )
    return ""


def _revert_reply(message: str, lang: str | None, *, apologetic: bool = True) -> str:
    """Canned reply for deterministic reverts (no model call), in the user's language."""
    if _KHMER_CHAR_RE.search(message or ""):
        return (
            "គ្មានបញ្ហាទេ — ខ្ញុំបានដាក់ទំព័ររបស់អ្នកត្រឡប់ទៅដូចមុនវិញហើយ។ និយាយម្តងទៀតដើម្បីត្រឡប់ក្រោយមួយជំហានទៀត។"
            if apologetic
            else "ខ្ញុំបានដាក់ទំព័ររបស់អ្នកត្រឡប់ទៅដូចមុនវិញហើយ។ និយាយម្តងទៀតដើម្បីត្រឡប់ក្រោយមួយជំហានទៀត។"
        )
    if lang == "nl":
        prefix = "Geen probleem! " if apologetic else ""
        return f"{prefix}Je pagina staat weer zoals hij was. Zeg het nog een keer als je nog een stap terug wilt."
    prefix = "No problem — I've" if apologetic else "I've"
    return f"{prefix} put your page back to how it was before. Say it again to go back another step."


# ---------------------------------------------------------------------------
# First-build image fill — on the onboarding intake, photos the user did not
# upload are generated (services/image_gen.py) so the page keeps image layouts
# instead of text-only fallbacks:
#   HERO  — whenever no banner/cover image was uploaded, even if the user
#           uploaded product photos (those go to the gallery, not the hero);
#   ABOUT — only when the user uploaded no photos at all (otherwise the about
#           section can use one of theirs).
# Only these slots, only once: everything else stays upload / ask-first.
# The temporary image URLs are made permanent by the Next.js builder proxy.
# ---------------------------------------------------------------------------

_AUTO_IMAGES_ENABLED = os.getenv("BUILDER_AUTO_IMAGES", "true").strip().lower() in ("1", "true", "yes")
_ONBOARDING_FINAL_RE = re.compile(r"guided multi-step flow[\s\S]*Current phase:\s*final", re.IGNORECASE)
# Photos the user uploaded during onboarding: URLs in the intake's "Banner
# images:"/"Additional images:" fields, or explicit [image: URL] attachments.
# The "Logo:" line is intentionally excluded because the frontend fills it from
# the page's existing footer logo when the user uploads nothing.
_PHOTO_FIELD_RE = re.compile(
    r"^\s*(?:Banner images|Additional images):[ \t]*(.*?)(?="
    r"^\s*[A-Za-z][^:\r\n]{0,80}:[ \t]*|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_LOGO_URL_RE = re.compile(
    r"^\s*Logo:\s*(https?://[^\s\"'<>\)\]]+)",
    re.IGNORECASE | re.MULTILINE,
)
_ATTACHED_PHOTO_RE = re.compile(
    r"(?:\[image:\s*|^\s*Attached images?\s*:\s*)"
    r"https?://[^\s\"'<>\)\]]+",
    re.IGNORECASE | re.MULTILINE,
)
# Just the intake's "Banner images:" field (the hero/cover photos).
_BANNER_FIELD_RE = re.compile(
    r"^\s*Banner images:[ \t]*(.*?)(?="
    r"^\s*[A-Za-z][^:\r\n]{0,80}:[ \t]*|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
# (section, field, image style to switch to when the AI's chosen style renders no image)
_AUTO_IMAGE_SLOTS = (("HERO", "image_url", 1), ("ABOUT", "image_url", 8))
_MIN_IMAGE_BUDGET_S = 20.0


def _user_uploaded_photos(message: str) -> bool:
    logo_urls = {
        match.group(1).rstrip(".,;")
        for match in _LOGO_URL_RE.finditer(message)
    }
    photo_message = message
    for logo_url in logo_urls:
        photo_message = photo_message.replace(logo_url, "")
    if _ATTACHED_PHOTO_RE.search(photo_message):
        return True
    return any(
        _URL_RE.search(field.group(1))
        for field in _PHOTO_FIELD_RE.finditer(photo_message)
    )


# Gallery photos already on the page (buildPageContext: 'item 1 "Loaf" image_url: "https://…"').
_PAGE_GALLERY_PHOTO_RE = re.compile(r'\bitem \d+ "[^"\n]*" image_url: "https?://')


# Gallery item photos in the page context ('item 3 "Name" image_url: "…"'). Hero
# and about images are left out: on a rebuild they are often AI-generated.
_PAGE_PHOTO_URL_RE = re.compile(r'\bitem \d+ "[^"\n]*" image_url: "(https?://[^"\s]+)"')
# This many photos or more: the full build's Code section is a photo gallery.
_PHOTO_GALLERY_MIN = int(os.getenv("BUILDER_PHOTO_GALLERY_MIN", "7"))
_PHOTO_GALLERY_MAX = 10


def _user_photo_urls(message: str, page_context: str | None) -> list[str]:
    """The user's photos, in order and without duplicates: uploaded with this
    message (onboarding fields, [image: …], attachments) and already in the
    page's galleries. The logo does not count."""
    message = message or ""
    logos = {m.group(1).rstrip(".,;") for m in _LOGO_URL_RE.finditer(message)}
    page_logo = re.findall(r"\blogo_url\"?\s*[:=]\s*\"?(https?://[^\s\"'<>\)\]]+)", page_context or "")
    logos |= {u.rstrip(".,;") for u in page_logo}
    urls: list[str] = []
    for url in _extract_message_image_urls(message) + _PAGE_PHOTO_URL_RE.findall(page_context or ""):
        url = url.rstrip(".,;")
        if url not in logos and url not in urls and not _NON_IMAGE_HOST_RE.search(url):
            urls.append(url)
    return urls


def _user_has_photos(message: str, page_context: str | None) -> bool:
    """Photos for a photo gallery: uploaded in this message (onboarding fields,
    [image: …], a chat attachment — the logo does not count) or already in the
    page's gallery."""
    message = message or ""
    if _user_uploaded_photos(message):
        return True
    logos = {m.group(1).rstrip(".,;") for m in _LOGO_URL_RE.finditer(message)}
    if any(url not in logos for url in _extract_message_image_urls(message)):
        return True
    return bool(_PAGE_GALLERY_PHOTO_RE.search(page_context or ""))


def _community_facts_note(facts: dict[str, Any], has_photos: bool) -> str:
    """What the community has, as a note at the end of the user message (it must
    outweigh an onboarding intake's fixed section list)."""
    lines: list[str] = []
    if facts.get("has_shop") is True:
        name = f' ("{facts["shop_name"]}")' if facts.get("shop_name") else ""
        lines.append(
            f"- Online shop: yes{name}. A full page build must include a product section: a GALLERY with "
            "section_subtype \"product\" — it shows the shop's products itself, so send only its title and description."
        )
    elif facts.get("has_shop") is False:
        lines.append("- Online shop: none. Do not put a product section (GALLERY \"product\") in a full page build.")
    episodes = facts.get("podcast_episodes")
    if isinstance(episodes, int) and episodes > 0:
        lines.append(f"- Podcast: {episodes} episodes. A full page build must include a PODCAST section.")
    if not has_photos:
        lines.append(
            "- Photos uploaded by the user: none. Do not put a photo gallery (GALLERY \"gallery\" or \"project\") "
            "in a full page build."
        )
    elif facts.get("has_shop") is True:
        lines.append(
            "- With both a photo gallery and a product section, the photo gallery is instance_key \"gallery\" and "
            "the product section \"gallery__2\"."
        )
    if not lines:
        return ""
    return (
        "\n\n(Community facts, checked by the service — they override any fixed section list above, including "
        "\"Do not add or remove any sections\":\n" + "\n".join(lines) + ")"
    )


# Onboarding product lines with an uploaded photo ("Product 1: … [image: URL]").
_PRODUCT_PHOTO_LINE_RE = re.compile(r"^\s*Product \d+:.*\[image:\s*https?://", re.IGNORECASE | re.MULTILINE)
# The intake text calls GALLERY a "Product/Services section" that "renders as
# product cards", which beats the system prompt's photo-gallery rule — so the
# rule is repeated at the end of the user message, where it outweighs it.
_ONBOARDING_PHOTO_GALLERY_NOTE = (
    "\n\n(Service note — overrides \"this renders as product cards\": the user uploaded photos with their "
    "Product lines, so the GALLERY is a photo gallery. Set its section_subtype to \"gallery\" (not "
    "\"product\") and give it one images[] item per Product line: its name, description and [image: ...] URL "
    "as image_url. Add no other photo gallery; a product section only as the community facts below say.)"
)


# Newer frontends write the photo-gallery rule into the intake themselves
# (buildAiIntakePrompt "GALLERY (photo gallery): ..."); the note is only for
# older ones. Delete the note once every deployed frontend sends that line.
_INTAKE_HAS_PHOTO_RULE_RE = re.compile(r"GALLERY \(photo gallery\):", re.IGNORECASE)


def _onboarding_photo_gallery_note(message: str) -> str:
    message = message or ""
    if (
        _ONBOARDING_FINAL_RE.search(message)
        and _PRODUCT_PHOTO_LINE_RE.search(message)
        and not _INTAKE_HAS_PHOTO_RULE_RE.search(message)
    ):
        return _ONBOARDING_PHOTO_GALLERY_NOTE
    return ""


# The wizard may skip the contact question. The intake's own reply instruction
# ("say the page is ready, offer to refine it") then wins over the system
# prompt's "say in reply that they can add it" — so it is repeated here.
# buildAiIntakePrompt writes "Contact information:\n<value>" and leaves the label
# out entirely when the user gave none.
_CONTACT_LINE_RE = re.compile(r"^\s*Contact information:", re.IGNORECASE | re.MULTILINE)
_ONBOARDING_NO_CONTACT_NOTE = (
    "\n\n(Service note: the user gave no contact details. Leave FOOTER email, phone, location and social_links "
    "out — never invent them — and in your reply also tell the user, in one short sentence, that they can add "
    "their contact details and social links in the footer.)"
)


def _onboarding_contact_note(message: str) -> str:
    message = message or ""
    if _ONBOARDING_FINAL_RE.search(message) and not _CONTACT_LINE_RE.search(message):
        return _ONBOARDING_NO_CONTACT_NOTE
    return ""


# "Product 1: <name> — <description> [image: <url>]", as LandingBuilderV2.js
# writes it (description and image are optional).
_PRODUCT_LINE_RE = re.compile(
    r"^\s*Product \d+:[ \t]*(?P<name>[^\r\n]*?)(?:[ \t]+—[ \t]+(?P<desc>[^\r\n]*?))?[ \t]*"
    r"(?:\[image:\s*(?P<url>https?://[^\s\]]+)\s*\])?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
# Photo-gallery layouts that need at least this many photos to look right
# (catalog "Picking layouts": Feature R / Feature Strip 5, Bento 6, Mosaic Grid 7).
_GALLERY_MIN_PHOTOS = {2: 5, 8: 5, 3: 6, 9: 7}


def _ensure_onboarding_photo_gallery(
    content: list[dict[str, Any]], message: str, has_shop: bool | None = None
) -> None:
    """Safety net for the onboarding intake: when the user uploaded photos with
    their Product lines, the page has a photo GALLERY holding them. Without a
    shop the page's GALLERY becomes that photo gallery; with a shop the product
    section stays and the photo gallery is added next to it.

    The frontend keeps a photo gallery only when section_subtype is exactly
    "gallery", and refills a missing image_url from the same position in its
    upload list — so the items must be one per Product line, in order, each
    with that line's exact URL. The model's own name/description are kept."""
    message = message or ""
    if not _ONBOARDING_FINAL_RE.search(message):
        return
    items = [
        {"image_url": m["url"] or "", "name": m["name"].strip(), "description": (m["desc"] or "").strip()}
        for m in _PRODUCT_LINE_RE.finditer(message)
        if m["name"].strip() or m["url"]
    ]
    if not any(i["image_url"] for i in items):
        return
    galleries = [s for s in content if normalize_section_type(s.get("type")) == "GALLERY"]
    gallery = next((g for g in galleries if g.get("section_subtype") == "gallery"), None)
    if gallery is None:
        first = galleries[0] if galleries else None
        if first is None:
            return
        if has_shop is True and first.get("section_subtype") == "product":
            gallery = {"type": "GALLERY", "section_subtype": "gallery", "style": 1, "is_hidden": False}
            if isinstance(first.get("colors"), dict):
                gallery["colors"] = dict(first["colors"])
            content.insert(content.index(first), gallery)
            logger.warning("Onboarding photos: added a photo GALLERY next to the shop's product section")
        else:
            logger.warning("Onboarding photos: switched GALLERY from %r to a photo gallery", first.get("section_subtype"))
            first["section_subtype"] = "gallery"
            gallery = first

    model_items = [i for i in gallery.get("images") or [] if isinstance(i, dict)]
    by_url = {i.get("image_url"): i for i in model_items if i.get("image_url")}
    merged: list[dict[str, Any]] = []
    for idx, line in enumerate(items):
        # The model's item for this line: same URL, else same position without a URL
        own = by_url.get(line["image_url"]) if line["image_url"] else None
        if own is None and idx < len(model_items) and not model_items[idx].get("image_url"):
            own = model_items[idx]
        own = own or {}
        merged.append({
            **own,
            "image_url": line["image_url"],
            "name": str(own.get("name") or "").strip() or line["name"],
            "description": str(own.get("description") or "").strip() or line["description"],
        })
    if [i.get("image_url") for i in model_items] != [i["image_url"] for i in merged]:
        logger.warning(
            "Onboarding photos: GALLERY items did not match the %d Product lines (order/URLs) — realigned",
            len(items),
        )
    gallery["images"] = merged
    photos = sum(1 for i in gallery["images"] if isinstance(i, dict) and i.get("image_url"))
    try:
        style = int(gallery.get("style") or 1)
    except (TypeError, ValueError):
        style = 1
    if photos < _GALLERY_MIN_PHOTOS.get(style, 0):
        gallery["style"] = 1  # Classic — fits any number of photos


def _apply_community_facts(content: list[dict[str, Any]], facts: dict[str, Any], has_photos: bool) -> None:
    """Safety net for a full page build, enforcing the community facts the model
    was told about: no photo gallery without photos, a product section only
    with an online shop (and always with one), a PODCAST section when the
    community has episodes. Added sections leave title/description out so the
    frontend fills in its defaults."""
    def _type(s: dict[str, Any]) -> str:
        return normalize_section_type(s.get("type"))

    def _has_photo(g: dict[str, Any]) -> bool:
        return any(isinstance(i, dict) and i.get("image_url") for i in g.get("images") or [])

    for g in [s for s in content if _type(s) == "GALLERY"]:
        product = g.get("section_subtype") == "product"
        if not product and not has_photos and not _has_photo(g):
            logger.warning("Community facts: removed a photo GALLERY — the user has no photos")
            content.remove(g)
        elif product and facts.get("has_shop") is False:
            logger.warning("Community facts: removed the product GALLERY — the community has no online shop")
            content.remove(g)
        elif product and facts.get("has_shop") is not True and not has_photos and not _has_photo(g):
            # Shop unknown and no images: the cards would show empty image boxes.
            logger.warning("Community facts: removed a product GALLERY — no shop confirmed and no images")
            content.remove(g)

    middle = [s for s in content if _type(s) not in ("HERO", "FOOTER")]
    colors = next((dict(s["colors"]) for s in middle if isinstance(s.get("colors"), dict)), None)
    footer_at = next((i for i, s in enumerate(content) if _type(s) == "FOOTER"), len(content))

    def _add(section: dict[str, Any], why: str) -> None:
        nonlocal footer_at
        if colors:
            section["colors"] = dict(colors)
        content.insert(footer_at, section)
        footer_at += 1
        logger.warning("Community facts: added %s", why)

    if facts.get("has_shop") is True and not any(
        _type(s) == "GALLERY" and s.get("section_subtype") == "product" for s in content
    ):
        _add({"type": "GALLERY", "section_subtype": "product", "style": 5, "is_hidden": False},
             "a product GALLERY for the community's online shop")
    episodes = facts.get("podcast_episodes")
    if isinstance(episodes, int) and episodes > 0 and not any(_type(s) == "PODCAST" for s in content):
        _add({"type": "PODCAST", "style": 1, "feed_type": "latest", "is_hidden": False},
             f"a PODCAST section ({episodes} episodes)")

    # Photo gallery first ("gallery"), then the product section ("gallery__2"):
    # the frontend's onboarding merge puts the uploads into the "gallery" instance.
    galleries = [s for s in content if _type(s) == "GALLERY"]
    if any(g.get("section_subtype") == "product" for g in galleries) and any(
        g.get("section_subtype") != "product" for g in galleries
    ):
        ordered = [g for g in galleries if g.get("section_subtype") != "product"] + [
            g for g in galleries if g.get("section_subtype") == "product"
        ]
        for n, g in enumerate(ordered, start=1):
            g["instance_key"] = "gallery" if n == 1 else f"gallery__{n}"


# ---------------------------------------------------------------------------
# Full page builds: code blocks + quality check
# ---------------------------------------------------------------------------

# A request for a whole page (EN/NL), like the frontend's FULL_PAGE_RE plus
# "build/create/make … landing page / website / homepage".
_FULL_BUILD_RE = re.compile(
    r"\b(whole|complete|full|entire|new|hele|volledige|nieuwe)\s+(?:[\w-]+\s+){0,2}"
    r"(landing\s*page|landingspagina|home\s*page|homepage|page|pagina|website|site)\b"
    r"|\b(build|create|make|generate|design|redesign|rebuild|bouw|maak|ontwerp)\b[^.?!\n]{0,40}"
    r"\b(landing\s*page|landingspagina|home\s*page|homepage|website|site|webpagina)\b"
    # Khmer: build / make / design (បង្កើត / ធ្វើ / រចនា) … website / page (គេហទំព័រ / វេបសាយ / ទំព័រ)
    r"|(?:បង្កើត|ធ្វើ|រចនា)[^.?!\n។]{0,40}(?:គេហទំព័រ|វេបសាយ|វ៉ិបសាយ|ទំព័រ)",
    re.IGNORECASE,
)


def _is_full_build_request(message: str) -> bool:
    message = message or ""
    return bool(_ONBOARDING_FINAL_RE.search(message) or _FULL_BUILD_RE.search(message))


_FULL_BUILD_CODE_BLOCKS_NOTE = (
    "\n\n(Service note for this full page build — overrides \"Don't add code blocks to a full page build unless "
    "asked\" and any rule against sending type 11: make the page feel designed, not templated. Be creative: a distinctive palette that suits this "
    "brand, an unexpected but fitting mix of layouts (no two pages alike), copy with personality — always within "
    "the rules above. Two sections next to each other never share the same background colour — alternate the "
    "palette's tints down the page. A FAQ has at least 4 questions. Write no opening hours, times, years, prices, addresses or "
    "phone numbers the user did not give — the page is checked for them. Add ONE Custom Code section to "
    "`content` (it counts as one of the middle sections), right after the section it relates to: "
    "{\"type\": 11, \"html\": \"...\", \"colors\": {\"bg\": \"<hex>\"}} — no code_blocks. Its html is real content "
    "about THIS brand, built only from what the user described (their products, services, how it works, what "
    "makes them different). For this page use this format: {format}. Make it look designed: the page's colours "
    "and fonts (a Google Fonts <link> is fine), clear hierarchy, balanced spacing (one centred wrapper, equal "
    "padding top and bottom, equal gaps), responsive (max-width: 100%; items stack on phones), its height set by "
    "the content (no vh heights). Colour it only with the CSS variables var(--page-text), var(--page-muted), "
    "var(--page-accent), var(--page-card) and var(--page-line) (the service fills them in for the background it "
    "lands on). Open it with a short uppercase eyebrow, a heading in the page's heading "
    "font and one line of intro, then the component; label every shape, chart or icon so nothing is a bare "
    "decoration. Bring it to life: a subtle entrance animation and smooth hover/active "
    "transitions (CSS, with @media (prefers-reduced-motion: reduce) turning them off). Interactive is welcome "
    "when it works — every clickable part must visibly change something inside the section through an inline "
    "<script> (show a panel, turn a wheel, open an item); no links, forms or buttons that lead nowhere. No emoji, "
    "no gradients, no pill badges, no mention of AI. Never invent facts in it (no prices, times, dates, numbers, "
    "reviews or names the user did not give). One self-contained snippet with an inline <style> and <script>; "
    "no images except uploaded URLs.)"
)
# Code section formats per kind of landing page. A format is drawn from a
# shuffle bag per page kind: every format is used once, in random order,
# before any repeats (and never twice in a row within a chat session) — with a
# single example the model made the same 3 cards on every page, and plain
# random draws still repeated often. Interactive formats go in the bag twice,
# so about two in three pages get one. Live examples of every format:
# https://claude.ai/artifact/2aQGea4gs3HAT5ULrfMPNJ
_ALL_KINDS = ("shop", "business", "news", "creator", "community", "education", "podcast", "portfolio",
              "food", "events")
# (key, interactive, kinds or ("any",), needs uploaded photos, instruction)
_CODE_FORMATS: tuple[tuple[str, bool, tuple[str, ...], bool, str], ...] = (
    # --- Animated, no clicking needed ---
    ("cards", False, ("any",), False,
     "three cards side by side, each with a small inline-SVG line icon that draws itself in, a short title and "
     "one sentence"),
    ("steps", False, ("business", "community", "education", "events", "food", "shop"), False,
     "numbered steps (3 or 4) showing how it works for the visitor, joined by a line that fills as the visitor "
     "scrolls past"),
    ("banner", False, ("any",), False,
     "a wide highlight banner: one bold statement of the brand's promise with a short supporting line and a "
     "decorative SVG shape that slowly drifts"),
    ("split", False, ("business", "community", "creator", "education", "shop"), False,
     "a two-column split: on one side who it is for, on the other what the visitor gets — short lines with "
     "check marks"),
    ("iconrow", False, ("any",), False,
     "an icon row of 4 short highlights (inline-SVG line icon that draws itself in + 2–4 words each) on a thin rule"),
    ("checklist", False, ("community", "education", "events", "food", "podcast"), False,
     "a \"what to expect\" checklist of 4–5 short items in a soft panel, ticks drawing in one after another"),
    ("timeline", False, ("business", "community", "food", "portfolio", "shop"), False,
     "a process timeline of 3–4 named stages (how it is made, how a visit or project goes), its line filling "
     "as the visitor scrolls — no times or dates"),
    ("ticker", False, ("creator", "food", "podcast", "shop"), False,
     "a thin band of 4–6 short brand phrases scrolling slowly sideways, pausing on hover, between two "
     "decorative rules"),
    ("waveform", False, ("podcast",), False,
     "the show's promise beside an animated audio waveform (CSS bars rising and falling) and three short lines "
     "on what listeners get"),
    # --- Interactive: the inline script makes every control work ---
    ("wheel", True, ("community", "creator", "education", "events", "food", "podcast"), False,
     "an interactive wheel beside a detail card. The wheel: 4–8 equal segments (seasons, topics, content "
     "pillars or modules) drawn as SVG ring paths in a 320×320 viewBox (outer radius 150, inner radius 72, "
     "computed in the script), max-width 360px, separated by 3px strokes in the section background colour. "
     "Every segment carries a short uppercase label (1–2 words, 11–12px, letter-spacing .06em) centred on the "
     "ring. All segments use the accent colour: inactive ones at fill-opacity .30 and .45 alternating with "
     "labels in the text colour, the active one at full accent with a white label, scaled 1.04 from the centre "
     "(never moved outward). The hub: a circle (radius 64) in the card colour with a 1px border and the wheel's "
     "name in the heading font. The detail card: the active segment's title, one or two sentences and a small "
     "\"2 / 6\" counter, fading in on change, with a quiet hint line \"Click a segment\" under it. Segments "
     "are focusable (tabindex 0, role button, Enter or Space); the first one starts active. Two columns on "
     "desktop, stacked on phones"),
    ("tabs", True, ("any",), False,
     "tabs: 3–4 tab buttons for the things the user offers; clicking one swaps the panel below with a short fade"),
    ("accordion", True, ("community", "education", "events", "food", "podcast", "shop"), False,
     "an accordion of 4–5 items (how it works, what to expect): click a row to open it with a smooth height "
     "transition, one open at a time"),
    ("flip", True, ("any",), False,
     "flip cards: 3–4 cards that turn over on click to show a short explanation on the back"),
    ("stepper", True, ("business", "community", "education", "events", "portfolio", "shop"), False,
     "a stepper: one step shown at a time with previous/next arrows and step dots, sliding between 3–5 steps"),
    ("filter", True, ("education", "food", "news", "podcast", "portfolio", "shop"), False,
     "a filter grid: 3–4 category chips that really filter 6 cards of the user's offerings (an \"All\" chip "
     "first), cards fading in as they appear"),
    ("picker", True, ("business", "creator", "education", "food", "podcast", "shop"), False,
     "a \"which one is for you?\" picker: 2 questions with tap answers (buttons, not a form) that recommend one "
     "of the user's real offerings in a result card"),
    ("diagram", True, ("business", "education", "food", "shop"), False,
     "a labelled diagram: an SVG drawing of the product or process with 3–4 numbered points that light up the "
     "matching explanation beside it"),
    ("toggle", True, ("business", "community", "creator", "education", "shop"), False,
     "a two-way toggle between two audiences (for example beginners / regulars, fans / brands) that swaps three "
     "short cards"),
    ("panels", True, ("community", "creator", "events", "food", "portfolio", "shop"), False,
     "expanding panels: 4 narrow panels in a row (collections, looks or stages), the hovered or clicked one "
     "widening to show its text (a column on phones)"),
    ("swatches", True, ("shop",), False,
     "a product spotlight: a CSS/SVG drawing of one product the user sells with 3–4 variant swatches that switch "
     "its colour, name and short description — only variants the user described"),
    ("bundle", True, ("food", "shop"), False,
     "a bundle builder: tap 3–5 of the user's products to add them to a box; a summary beside it lists the picks "
     "(no prices)"),
    ("glossary", True, ("community", "education", "news"), False,
     "an explainer paragraph with 3–5 key terms underlined; clicking a term opens its plain-language "
     "definition below the text"),
    ("briefing", True, ("news",), False,
     "\"the story so far\": 3–5 short briefing cards on what the platform covers, one at a time, with a "
     "progress bar and next/previous arrows"),
    ("topics", True, ("news", "podcast"), False,
     "a topic guide: topic chips that switch a list of 3–4 themes the user covers; a small CSS waveform or "
     "pulse animates beside the active topic"),
    ("flashcards", True, ("education",), False,
     "a deck of 4–6 flashcards on the subject the user teaches: click to flip, arrows to move, a \"2 / 6\" count"),
    ("path", True, ("community", "education"), False,
     "a learning or member path: 4–6 connected nodes on an SVG line; clicking a node shows what that stage "
     "covers"),
    ("collab", True, ("creator",), False,
     "a \"work with me\" tab set: 2–4 kinds of collaboration the user offers, each panel with what a brand or "
     "fan gets"),
    ("beforeafter", True, ("food", "portfolio", "shop"), True,
     "a before/after slider: two of the user's uploaded photos stacked, a draggable handle revealing one over "
     "the other"),
    ("hotspots", True, ("food", "portfolio", "shop"), True,
     "an uploaded photo with 3–4 pins; tapping a pin shows a short label about that part of the picture"),
)

# Onboarding "Platform type:" answers -> page kind
_PLATFORM_KINDS = {
    "online shop": "shop", "personal brand": "creator", "business website": "business",
    "blog or news platform": "news", "creator or influencer page": "creator", "community platform": "community",
    "educational platform": "education", "podcast or media platform": "podcast",
    "portfolio website": "portfolio", "restaurant or cafe": "food", "nonprofit or organization": "community",
    "event or booking platform": "events",
}
# Chat requests: words that point to a kind (EN/NL/KM)
_KIND_WORDS = {
    "shop": r"shop|store|webshop|e-?commerce|sell\w*|products?|winkel|boutique|cloth\w*|fashion|apparel|"
            r"garments?|kleding|jewel\w*|cosmetics|skincare|ហាង|លក់|សម្លៀកបំពាក់",
    "business": r"business|company|agency|services?|consult\w*|firm|bedrijf|ក្រុមហ៊ុន",
    "news": r"news|magazine|journal\w*|publisher|articles?|blog|nieuws|ព័ត៌មាន",
    "creator": r"creator|influencer|youtuber|tiktok|instagram|streamer|vlog\w*|personal brand",
    "community": r"community|association|club|ngo|non-?profit|foundation|members|volunteer\w*|vereniging|សហគមន៍",
    "education": r"course|school|academy|classes|tutor\w*|training|lessons?|students|cursus|សាលា|វគ្គ",
    "podcast": r"podcast|episodes?|listeners",
    "portfolio": r"portfolio|photograph\w*|designer|illustrat\w*|architect\w*|freelanc\w*",
    "food": r"restaurant|cafe|café|coffee|bakery|kitchen|menu|catering|food|eten|ភោជនីយដ្ឋាន|កាហ្វេ",
    "events": r"events?|festival|conference|booking|tickets?|wedding|concert",
}
_KIND_RES = {k: re.compile(rf"\b(?:{v})\b", re.IGNORECASE) for k, v in _KIND_WORDS.items()}
_PLATFORM_TYPE_RE = re.compile(r"^Platform type:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_USER_ANSWER_RE = re.compile(r"^(?:Brand name|Platform details):\s*(.*(?:\n(?![A-Z][\w ]+:|- |\s*$).*)*)", re.MULTILINE)


def _page_kind(message: str, facts: dict[str, Any] | None = None) -> str:
    """The kind of landing page being built (shop, podcast, news, ...), or
    "any". The onboarding wizard's "Platform type:" wins; otherwise words in the
    user's own text plus the community facts (a shop, podcast episodes)."""
    message = message or ""
    m = _PLATFORM_TYPE_RE.search(message)
    if m and m.group(1).strip().lower() in _PLATFORM_KINDS:
        return _PLATFORM_KINDS[m.group(1).strip().lower()]
    # Onboarding text also lists every template's description: read only the answers.
    text = " ".join(_USER_ANSWER_RE.findall(message)) if _ONBOARDING_FINAL_RE.search(message) else message
    scores = {k: len(r.findall(text)) for k, r in _KIND_RES.items()}
    facts = facts or {}
    if isinstance(facts.get("podcast_episodes"), int) and facts["podcast_episodes"] > 0:
        scores["podcast"] += 2
    if facts.get("has_shop") is True:
        scores["shop"] += 1
    kind, score = max(scores.items(), key=lambda kv: kv[1])
    return kind if score > 0 else "any"


def _formats_for(kind: str, has_photos: bool) -> list[tuple[str, str]]:
    """(key, instruction) of every format that fits this kind of page."""
    return [
        (key, text) for key, _interactive, kinds, needs_photos, text in _CODE_FORMATS
        if (kind == "any" or "any" in kinds or kind in kinds) and (has_photos or not needs_photos)
    ]


_last_code_block_format: dict[str, tuple[float, str]] = {}
_code_block_format_bags: dict[tuple[str, bool], list[str]] = {}
_code_block_format_lock = threading.Lock()


# Colours are Bob's choice ("Let AI choose" in onboarding, or a build request
# that names no colour): the frontend then sends no theme, and the model fell
# back to white middle sections that the adjacent-background fix turned grey.
_THEME_CHOSEN_RE = re.compile(r"Theme colou?r chosen by the user", re.IGNORECASE)
_COLOUR_WISH_RE = re.compile(
    r"#[0-9a-f]{3}\b|#[0-9a-f]{6}\b|\b(?:colou?rs?|palette|theme|white|gr[ae]y|black|red|blue|green|yellow|orange|"
    r"purple|violet|pink|brown|beige|cream|gold|silver|navy|teal|turquoise|cyan|maroon|olive|lime|coral|"
    r"pastel|monochrome|minimal(?:ist)?|neutral|kleur(?:en)?|wit|grijs|zwart|rood|blauw|groen|geel|oranje|"
    r"paars|roze|bruin)\b|ពណ៌",
    re.IGNORECASE,
)


def _ai_picks_colours(message: str) -> bool:
    """True when the user left the colours to Bob: no theme chosen in the
    onboarding wizard and no colour named in the request ("Brand colors:" from
    the wizard counts as named)."""
    message = message or ""
    if _THEME_CHOSEN_RE.search(message):
        return False
    if _ONBOARDING_FINAL_RE.search(message):
        # The wizard's own instructions talk about colours and palettes: only
        # the user's answers count.
        return not re.search(r"^Brand colou?rs?:\s*\S", message, re.IGNORECASE | re.MULTILINE)
    return not _COLOUR_WISH_RE.search(message)


# Curated themes — mirrors fe-serey-web LandingBuilderV2.js CURATED_THEMES and
# applyCuratedThemeToSections(): hero and middle sections alternate section_bg /
# bg_alt in page order, the footer gets a dark variant of bg_alt. When the user
# leaves the colours to Bob (no theme, no colour named) the service draws one at
# random: left to choose, the model picked white/light pages every time.
# Themes whose two backgrounds are both light are left out of the draw.
_CURATED_THEMES: tuple[dict[str, str], ...] = (
    {"id": "midnight-slate", "label": "Midnight & Slate", "accent": "#38bdf8", "section_bg": "#1e293b", "bg_alt": "#111827"},
    {"id": "cherry-cream", "label": "Cherry & Cream", "accent": "#670626", "section_bg": "#f7f1ea", "bg_alt": "#670626"},
    {"id": "ice-chocolate", "label": "Ice & Chocolate", "accent": "#47230f", "section_bg": "#b5d0f3", "bg_alt": "#47230f"},
    {"id": "modern-azure", "label": "Modern Azure", "accent": "#000f0f", "section_bg": "#68c7ec", "bg_alt": "#000f0f"},
    {"id": "milk-sea", "label": "Milk & Sea", "accent": "#1d1c73", "section_bg": "#f8f6fd", "bg_alt": "#1d1c73"},
    {"id": "cherry-matcha", "label": "Cherry & Matcha", "accent": "#670626", "section_bg": "#bad797", "bg_alt": "#670626"},
    {"id": "royal-cobalt-glacier-mist", "label": "Royal Cobalt & Glacier Mist", "accent": "#014aad", "section_bg": "#cbdfee", "bg_alt": "#014aad"},
    {"id": "french-blue-creamy-avocado", "label": "French Blue & Creamy Avocado", "accent": "#0055a4", "section_bg": "#dcf4a2", "bg_alt": "#0055a4"},
    {"id": "icing-warm-wood", "label": "Icing & Warm Wood", "accent": "#3b1b0e", "section_bg": "#dcc099", "bg_alt": "#3b1b0e"},
    {"id": "saffron-ink", "label": "Saffron & Ink", "accent": "#b7791f", "section_bg": "#fdf1d3", "bg_alt": "#1f2a44"},
    {"id": "jade-rice-paper", "label": "Jade & Rice Paper", "accent": "#0f7a5c", "section_bg": "#edf6f0", "bg_alt": "#0f5c4a"},
    {"id": "lotus-plum", "label": "Lotus & Plum", "accent": "#a8326e", "section_bg": "#fbeef3", "bg_alt": "#5b1d4a"},
    {"id": "mekong-sunset", "label": "Mekong Sunset", "accent": "#c2410c", "section_bg": "#ffe8d9", "bg_alt": "#8a2f12"},
    {"id": "ocean-sand", "label": "Ocean & Sand", "accent": "#0e7490", "section_bg": "#f2e8d5", "bg_alt": "#0b4f6c"},
    {"id": "lime-charcoal", "label": "Lime & Charcoal", "accent": "#4d7c0f", "section_bg": "#eef4d4", "bg_alt": "#232624"},
    {"id": "lavender-night", "label": "Lavender & Night", "accent": "#5b4bc4", "section_bg": "#ebe7fb", "bg_alt": "#2b2757"},
    {"id": "mango-leaf", "label": "Mango & Leaf", "accent": "#b45309", "section_bg": "#fff0c2", "bg_alt": "#2f5d32"},
)
_last_build_theme: dict[str, tuple[float, str]] = {}


def _pick_build_theme(session_id: str = "") -> dict[str, str]:
    """A random curated theme, never the one this chat session got last."""
    last = _last_build_theme.get(session_id, (0.0, ""))[1]
    theme = random.choice([t for t in _CURATED_THEMES if t["id"] != last] or list(_CURATED_THEMES))
    if session_id:
        _remember_session_value(_last_build_theme, session_id, theme["id"])
    return theme


def _hex_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    def lin(v: str) -> float:
        c = int(v, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(h[0:2]) + 0.7152 * lin(h[2:4]) + 0.0722 * lin(h[4:6])


def _theme_text(bg: str) -> dict[str, str]:
    # Same split as the frontend's themeTextColorsFor(): ~0.179 is where dark and
    # light text have equal contrast.
    if _hex_luminance(bg) > 0.179:
        return {"title": "#0f172a", "subtitle": "#1e293b", "body": "#334155"}
    return {"title": "#f8fafc", "subtitle": "#e2e8f0", "body": "#cbd5e1"}


def _footer_bg(bg_alt: str) -> str:
    """Dark variant of bg_alt (frontend darkenForFooter: lightness 5–14%)."""
    import colorsys
    r, g, b = (int(bg_alt[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s_ = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(h, max(0.05, min(l - 0.12, 0.14)), s_)
    return "#" + "".join(f"{round(v * 255):02x}" for v in (r, g, b))


_CHOSEN_THEME_RE = re.compile(
    r'Theme colou?r chosen by the user: "([^"]*)" \(background (#[0-9a-fA-F]{6}), second background '
    r'(#[0-9a-fA-F]{6}), accent (#[0-9a-fA-F]{6})\)'
)


def _chosen_theme(message: str) -> dict[str, str] | None:
    """The theme the onboarding wizard sent (picked by the user, or drawn at
    random for "Let AI choose"). The frontend repaints the page with it after
    the build, so the service applies the same alternation first."""
    m = _CHOSEN_THEME_RE.search(message or "")
    if not m:
        return None
    return {"id": "chosen", "label": m.group(1), "section_bg": m.group(2).lower(),
            "bg_alt": m.group(3).lower(), "accent": m.group(4).lower()}


def _ai_palette_note(theme: dict[str, str]) -> str:
    return (
        f"\n\n(Colour theme — the user let you choose, and the theme for this page is \"{theme['label']}\": "
        f"backgrounds alternate {theme['section_bg']} and {theme['bg_alt']} down the page, starting with HERO; "
        f"accent {theme['accent']} on every section; the footer a dark shade of {theme['bg_alt']}. Use exactly "
        "these colours. Text is dark on the light background and light on the dark one.)"
    )


def _apply_build_theme(content: list[dict[str, Any]], theme: dict[str, str], page_owned: frozenset[str]) -> None:
    """Paint the page with a curated theme the way the frontend's
    applyCuratedThemeToSections() does. Sections over a background image keep
    no bg and get white text; the user's own Code sections are left alone."""
    image_text = {"title": "#ffffff", "subtitle": "rgba(255,255,255,0.9)", "body": "rgba(255,255,255,0.8)"}
    alt = False
    for section in content:
        if section.get("is_hidden"):
            continue
        stype = normalize_section_type(section.get("type"))
        if stype == catalog.CODE_SECTION_TYPE and (section.get("instance_key") or "code") in page_owned:
            continue
        keys = catalog.SECTION_COLOR_KEYS.get(stype, ("title", "bg", "accent"))
        colors = dict(section.get("colors") or {})
        if stype == "FOOTER":
            bg = _footer_bg(theme["bg_alt"])
            text = _theme_text(bg)
        elif section.get("bg_image_url") or (stype == "HERO" and int(section.get("style") or 1) in (1, 2)):
            # Photo background (hero Backdrop/Cinematic gets one): keep its
            # alternation slot free and use white text over the dark overlay.
            colors.pop("bg", None)
            colors.update({k: v for k, v in image_text.items() if k in keys})
            if "accent" in keys:
                colors["accent"] = theme["accent"]
            section["colors"] = colors
            continue
        else:
            bg = theme["bg_alt"] if alt else theme["section_bg"]
            alt = not alt
            text = _theme_text(bg)
        colors["bg"] = bg
        if "accent" in keys:
            colors["accent"] = theme["accent"]
        for k, v in text.items():
            if k in keys:
                colors[k] = v
        colors.pop("card_bg", None)
        section["colors"] = {k: v for k, v in colors.items() if k in keys or k == "bg"}


def _photo_gallery_format(urls: list[str]) -> str:
    listed = "\n".join(f"  {i}. {u}" for i, u in enumerate(urls[:_PHOTO_GALLERY_MAX], 1))
    return (
        f"a photo gallery of expanding panels built from the user's {min(len(urls), _PHOTO_GALLERY_MAX)} "
        f"uploaded photos, one per panel, in this order:\n{listed}\n"
        "Each panel shows its photo filling it (background-image: url(...); background-size: cover; "
        "background-position: center). The hovered, focused or clicked panel widens to about four times the "
        "others; the first one starts open. Collapsed panels show only the photo and a small number — no text "
        "that could be cut off. The open panel may show a one-line caption at the bottom, but only when the "
        "image analysis or the user says what that photo shows; otherwise no caption. Panels are buttons with "
        "an aria-label, and arrow keys move between them. On phones: a horizontal scroll-snap row of tall "
        "cards instead. Use no other image URLs"
    )


def _draw_code_format(
    session_id: str = "",
    kind: str = "any",
    has_photos: bool = False,
    photo_urls: list[str] | None = None,
) -> str:
    """One Code section format: a photo gallery when the user has enough
    photos, else one for this kind of page from that kind's shuffle bag."""
    if photo_urls and len(photo_urls) >= _PHOTO_GALLERY_MIN:
        return _photo_gallery_format(photo_urls)
    last = _last_code_block_format.get(session_id, (0.0, ""))[1]
    texts = dict(_formats_for(kind, has_photos))
    interactive = {key for key, is_interactive, *_rest in _CODE_FORMATS if is_interactive}
    with _code_block_format_lock:
        bag = _code_block_format_bags.setdefault((kind, has_photos), [])
        if not bag:
            keys = [k for k in texts for _ in range(2 if k in interactive else 1)]
            bag.extend(random.sample(keys, len(keys)))
        # The next format in the bag that this session did not just get
        pick = next((i for i, k in enumerate(bag) if k != last), 0)
        choice = bag.pop(pick)
    if session_id:
        _remember_session_value(_last_code_block_format, session_id, choice)
    return texts[choice]


def _full_build_note(
    session_id: str = "",
    kind: str = "any",
    has_photos: bool = False,
    photo_urls: list[str] | None = None,
) -> str:
    """The full-build service note with one Code section format."""
    return _FULL_BUILD_CODE_BLOCKS_NOTE.replace(
        "{format}", _draw_code_format(session_id, kind, has_photos, photo_urls)
    )


# An edit that asks for a code / HTML / custom section: without the full-build
# note the model added an empty Code section (title and colours, no html).
_CODE_SECTION_ASK_RE = re.compile(
    r"\b(?:code|html|custom|interactive|widget)\b[^.?!\n]{0,30}\b(?:section|block|part)\b"
    r"|\b(?:section|block)\b[^.?!\n]{0,20}\b(?:with|of|in)\s+(?:code|html)\b",
    re.IGNORECASE,
)
_CODE_SECTION_EDIT_NOTE = (
    "\n\n(Service note — the user asked for a Custom Code section. Send an add_block patch with \"type\": 11 "
    "and updates {\"html\": \"<the complete snippet>\", \"colors\": {\"bg\": \"<a background this page already "
    "uses>\"}} and write the html yourself — never an empty section, unless the user says they will write "
    "the code. Its content is about THIS page: the brand, offer and copy in the page state. For this section "
    "use this format: {format}. Open it with a short uppercase eyebrow, a heading and one line of intro; colour "
    "it only with var(--page-text), var(--page-muted), var(--page-accent), var(--page-card) and "
    "var(--page-line); every clickable part must work through the inline <script>; no emoji, no gradients, no "
    "vh heights.)"
)


def _code_section_edit_note(message: str, session_id: str, kind: str, has_photos: bool) -> str:
    """The note for an edit turn that asks for a Code section, else ""."""
    if not _CODE_SECTION_ASK_RE.search(message or ""):
        return ""
    return _CODE_SECTION_EDIT_NOTE.replace("{format}", _draw_code_format(session_id, kind, has_photos))
def _code_block_problem(html: Any, known_text: str = "") -> str | None:
    """Why HTML Bob wrote cannot stay, or None. Interactive parts are welcome
    when its own script makes them work; controls that do nothing are not."""
    return dead_controls(html, known_text)


_QUALITY_FILLER = (
    "passionate", "we strive", "one-stop shop", "elevate", "unlock", "seamless", "cutting-edge",
    "world-class", "your journey", "look no further",
)
_QUALITY_PLACEHOLDER_RE = re.compile(
    r"lorem ipsum|\bsection title\b|\byour (title|headline|tagline|company|brand|business) (here|name)\b"
    r"|\bplaceholder\b|\bsample text\b|\btext goes here\b|\byour text here\b",
    re.IGNORECASE,
)
# Facts the model must not invent: (label, pattern). A hit only counts when the
# matched text appears nowhere in what the user wrote or the page state.
_INVENTED_FACT_RES = (
    ("an email address", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("a phone number", re.compile(r"\+?\d[\d ().-]{7,}\d")),
    ("a street address", re.compile(
        r"\b(?:street|st\.|road|rd\.|avenue|ave\.|boulevard|blvd|straat|weg|laan)\s*#?\d+\b"
        r"|\b\d+\s+(?:street|road|avenue)\b|ផ្លូវ\s*\d+",
        re.IGNORECASE,
    )),
    ("opening hours or times", re.compile(
        r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm)\b|\b\d{1,2}:\d{2}\b|\b\d{1,2}\.\d{2}\s?(?:uur|h)\b|\b\d{1,2}\s?uur\b",
        re.IGNORECASE,
    )),
    ("a founding year", re.compile(
        r"\b(?:since|sinds|founded in|established in|est\.?|opgericht in|baking since)\s+(?:19|20)\d{2}\b",
        re.IGNORECASE,
    )),
    ("a price", re.compile(r"(?:[$€៛]|\bUSD|\bKHR|\briel)\s?\d|\b\d+(?:[.,]\d+)?\s?(?:[$€៛]|USD\b|KHR\b|riels?\b)", re.IGNORECASE)),
)
_HTML_URL_RE = re.compile(
    r"""(?:src|href)\s*=\s*["']?(https?://[^"'\s>]+)|url\(\s*["']?(https?://[^"')\s]+)""", re.IGNORECASE
)
_ALLOWED_HTML_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")
_TAG_RE = re.compile(r"<[^>]+>")
_FIXED_SECTION_LIST_RE = re.compile(r"exactly \d+ sections in this order", re.IGNORECASE)


def _blueprint_texts(section: Any) -> list[str]:
    """Visitor-facing text of a section (titles, copy, items), not URLs/colours."""
    out: list[str] = []
    if isinstance(section, dict):
        for key, value in section.items():
            if key in ("colors", "text_styles", "type", "style", "instance_key", "section_subtype", "feed_type",
                       "video_mode", "image_url", "image_url_2", "bg_image_url", "logo_url", "is_hidden"):
                continue
            out += _blueprint_texts(value)
    elif isinstance(section, list):
        for value in section:
            out += _blueprint_texts(value)
    elif isinstance(section, str):
        out.append(section)
    return out


def _quality_problems(data: dict[str, Any], known_text: str, message: str, theme_set: bool = False) -> list[str]:
    """Concrete problems with a full page answer, written as instructions for the
    model. Empty when the page passes."""
    blueprint = data.get("blueprint")
    content = blueprint.get("content") if isinstance(blueprint, dict) else None
    if not isinstance(content, list) or not content:
        return []
    problems: list[str] = []
    known = (known_text or "").lower()
    # Code sections hold HTML, not section copy: checked below with code blocks.
    is_code = [isinstance(s, dict) and normalize_section_type(s.get("type")) == catalog.CODE_SECTION_TYPE
               for s in content]
    sections = [s for s, code in zip(content, is_code) if isinstance(s, dict) and not code]
    present = {normalize_section_type(s.get("type")) for s in sections if not s.get("is_hidden")}
    for must in ("HERO", "FOOTER"):
        if must not in present:
            problems.append(f"the page has no {must} — a full page starts with HERO and ends with FOOTER")
    middle = [s for s in content if isinstance(s, dict)
              and normalize_section_type(s.get("type")) not in ("HERO", "FOOTER") and not s.get("is_hidden")]
    # (Neighbouring sections with the same background are not a retry reason:
    # separate_adjacent_backgrounds() always fixes them, without a second call.)
    if not _FIXED_SECTION_LIST_RE.search(message or "") and not 4 <= len(middle) <= 7:
        problems.append(f"the page has {len(middle)} middle sections — use 4 to 7 that fit the brand")
    if _ai_picks_colours(message) and not theme_set:
        middle_bgs = [(s.get("colors") or {}).get("bg") for s in middle if isinstance(s.get("colors"), dict)]
        if middle_bgs and all(is_neutral(bg) or not bg for bg in middle_bgs):
            problems.append(
                "every middle section is white or grey — the user let you choose the colours: pick a palette for "
                "this brand and alternate its section_bg and bg_alt tints of the brand hue"
            )
    for s in sections:
        stype = normalize_section_type(s.get("type"))
        title = str(s.get("title") or "").strip()
        if stype == "HERO" and (not title or title.lower().startswith(("welcome", "welkom"))):
            problems.append("the HERO title is empty or starts with \"Welcome\" — write a specific 2–8 word headline")
        elif stype not in ("FOOTER",) and not title:
            problems.append(f"the {stype} section has no title")
        if stype == "FAQ" and len([i for i in s.get("faq_items") or [] if isinstance(i, dict)]) < 4:
            problems.append("the FAQ has fewer than 4 questions — write 4 to 6 real visitor questions")
        if stype == "TESTIMONIALS" and "testimonials:" not in known:
            roles = [str(i.get("role") or "") for i in s.get("testimonial_items") or [] if isinstance(i, dict)]
            if any(r != "Sample review" for r in roles):
                problems.append("the user gave no reviews, so every testimonial needs role \"Sample review\"")

    texts = [t for s in sections for t in _blueprint_texts(s)]
    code_html = [
        ("the Custom Code section", s) for s, code in zip(content, is_code) if code and s.get("html")
    ] + [
        (f"the code block under {b.get('section') or 'the page'}", b)
        for b in data.get("code_blocks") or [] if isinstance(b, dict) and b.get("action") == "add"
    ]
    for label, block in code_html:
        html = block.get("html")
        if not isinstance(html, str):
            continue
        texts.append(_TAG_RE.sub(" ", html))
        reason = _code_block_problem(html, known_text)
        if reason:
            problems.append(
                f"{label} has {reason} — make every clickable part work with the inline script, or remove it"
            )
        for style_problem in code_style_problems(html, known_text):
            problems.append(f"{label} has {style_problem}")
        for url in (a or b for a, b in _HTML_URL_RE.findall(html)):
            host = (urlparse(url).hostname or "").lower()
            if url.lower() not in known and not host.endswith(_ALLOWED_HTML_HOSTS):
                problems.append(f"a code block links to {url}, which the user never gave — remove it")
    joined = "\n".join(texts)
    low = joined.lower()
    for phrase in _QUALITY_FILLER:
        if phrase in low:
            problems.append(f"the copy uses the filler phrase \"{phrase}\" — rewrite it concretely")
    if _QUALITY_PLACEHOLDER_RE.search(joined):
        problems.append("the copy still has placeholder text — replace it with real copy")
    for label, pattern in _INVENTED_FACT_RES:
        invented = sorted({m.group(0).strip() for m in pattern.finditer(joined) if m.group(0).strip().lower() not in known})
        if invented:
            problems.append(
                f"the copy invents {label} the user never gave ({', '.join(invented[:3])}) — remove it or "
                "write the sentence without it"
            )
    return list(dict.fromkeys(problems))


def _quality_retry_note(problems: list[str]) -> str:
    return (
        "\n\n(Quality check — your page is not finished yet. Fix exactly these problems and send the whole "
        "corrected answer again, keeping everything else:\n- " + "\n- ".join(problems) + ")"
    )


def _parse_model_json(raw: str) -> dict[str, Any] | None:
    """A JSON object from model text (fences/trailing prose tolerated), or None."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    brace = text.find("{")
    if brace == -1:
        return None
    try:
        parsed, _end = json.JSONDecoder().raw_decode(text, brace)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _user_uploaded_banner(message: str) -> bool:
    return any(_URL_RE.search(field.group(1)) for field in _BANNER_FIELD_RE.finditer(message))


def _auto_image_slots(message: str) -> tuple[str, ...]:
    """Section types ("HERO", "ABOUT") whose photo is generated this turn; () for none."""
    message = message or ""
    if not (_AUTO_IMAGES_ENABLED and _ONBOARDING_FINAL_RE.search(message)):
        return ()
    slots: list[str] = []
    if _user_uploaded_banner(message):
        logger.info("First-build HERO image skipped: the user uploaded a banner image")
    else:
        slots.append("HERO")
    if _user_uploaded_photos(message):
        logger.info("First-build ABOUT image skipped: the user uploaded photos during onboarding")
    else:
        slots.append("ABOUT")
    return tuple(slots)


def _fallback_image_prompt(section: dict[str, Any], slot_type: str) -> str:
    """Used when the builder model returned no image_prompts entry."""
    context = " ".join(
        str(section.get(k) or "") for k in ("title", "subtitle", "description")
    ).strip()[:400]
    role = "wide hero banner" if slot_type == "HERO" else "about-section photo"
    return f"Atmospheric {role} for the website of this business: {context}."


async def _auto_fill_key_images(
    raw_blueprint: dict[str, Any],
    image_prompts: Any,
    deadline: float,
    prefetched: dict[str, str] | None = None,
    slots: tuple[str, ...] = ("HERO", "ABOUT"),
) -> list[GeneratedImage]:
    """Generate the empty photos of `slots` (hero/about) in parallel and place them in the
    blueprint. A section is switched to an image layout ONLY when its image
    arrived, so a failed generation leaves the AI's text-led layout intact."""
    remaining = deadline - time.monotonic()
    if not prefetched and remaining < _MIN_IMAGE_BUDGET_S:
        logger.warning("Skipping first-build images: only %.0fs of budget left", remaining)
        return []
    prompts = image_prompts if isinstance(image_prompts, dict) else {}
    jobs: list[tuple[dict[str, Any], str, str, int, str]] = []
    claimed: set[str] = set()
    for section in raw_blueprint.get("content") or []:
        stype = normalize_section_type(section.get("type"))
        for slot_type, field, image_style in _AUTO_IMAGE_SLOTS:
            if slot_type not in slots:
                continue
            if stype != slot_type or slot_type in claimed or section.get("is_hidden"):
                continue
            claimed.add(slot_type)  # first visible instance only
            if str(section.get(field) or "").strip():
                continue  # already has an image (echoed user upload)
            prompt = str(prompts.get(slot_type.lower()) or "").strip() or _fallback_image_prompt(section, slot_type)
            jobs.append((section, stype, field, image_style, prompt))
    if not jobs:
        return []

    generated_jobs = [
        asyncio.to_thread(
            image_gen.generate_image,
            prompt,
            "16:9",
            min(image_gen.IMAGE_TIMEOUT_S, max(5.0, deadline - time.monotonic() - 5)),
        )
        for section, slot_type, field, image_style, prompt in jobs
        if not prefetched or slot_type not in prefetched
    ]
    generated_results = await asyncio.gather(*generated_jobs, return_exceptions=True)
    generated_iter = iter(generated_results)
    results: list[Any] = [
        prefetched[slot_type] if prefetched and slot_type in prefetched else next(generated_iter)
        for _section, slot_type, _field, _image_style, _prompt in jobs
    ]
    generated: list[GeneratedImage] = []
    for (section, stype, field, image_style, prompt), result in zip(jobs, results):
        if isinstance(result, BaseException):
            logger.warning("First-build %s image failed: %s", stype, result)
            continue
        fallback_style = int(section.get("style") or 1)
        if field not in get_rendered_fields(stype, fallback_style):
            section["style"] = image_style
        section[field] = result
        generated.append(GeneratedImage(
            section=stype.lower(),
            field=field,
            url=result,
            instance_key=section.get("instance_key") or None,
            style=int(section["style"]),
            fallback_style=fallback_style,
            prompt=prompt,
        ))
    logger.info("First-build images: %d/%d generated", len(generated), len(jobs))
    return generated


async def _prefetch_auto_images(message: str, deadline: float, slots: tuple[str, ...]) -> dict[str, str]:
    """Generate the first-build images of `slots` alongside the slower blueprint model call."""
    context = " ".join((message or "").split())[:1400]
    prompts = {
        "HERO": (
            f"Clean wide editorial hero background photograph, image-only, for the business "
            f"described here: {context}. Show only the real-world products, materials, setting, "
            "and atmosphere. Leave a calm, empty area (plain wall, sky or tabletop) on one side. "
            "Do not create a website mockup, advertisement, poster, banner design, or promotional "
            "graphic."
        ),
        "ABOUT": (
            f"Clean editorial about-section photograph, image-only, for the business described "
            f"here: {context}. Show only the real-world products, materials, setting, and "
            "craftsmanship. Do not create a website mockup, advertisement, poster, banner design, "
            "promotional graphic, or text-bearing composition."
        ),
    }
    prompts = {slot: prompt for slot, prompt in prompts.items() if slot in slots}
    results = await asyncio.gather(
        *(
            asyncio.to_thread(
                image_gen.generate_image,
                prompt,
                "16:9",
                min(image_gen.IMAGE_TIMEOUT_S, max(5.0, deadline - time.monotonic() - 5)),
            )
            for prompt in prompts.values()
        ),
        return_exceptions=True,
    )
    prefetched: dict[str, str] = {}
    for slot_type, result in zip(prompts, results):
        if isinstance(result, BaseException):
            logger.warning("Prefetched first-build %s image failed: %s", slot_type, result)
        else:
            prefetched[slot_type] = result
    return prefetched


def _last_change_was_color_only(session_id: str) -> bool:
    entry = _last_change_color_only.get(session_id)
    if not entry:
        return False
    ts, color_only = entry
    if time.time() - ts > _PREV_CONTEXT_TTL_SECS:
        _last_change_color_only.pop(session_id, None)
        return False
    return color_only


def _verify_api_key(x_serey_api_key: str = Header(default="")) -> None:
    if _CHAT_API_KEY and x_serey_api_key != _CHAT_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: invalid API key")


def _parse_page_context_json(page_context: str | None) -> dict[str, Any] | None:
    if not page_context:
        return None
    try:
        parsed = json.loads(page_context)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_section_styles(layout_sections: list[dict[str, Any]]) -> None:
    for section in layout_sections:
        section_type = normalize_section_type(section.get("type"))
        if not section_type:
            continue
        style, changed = normalize_style(section_type, section.get("style"), section.get("section_subtype"))
        if changed:
            logger.warning(
                "Adjusted invalid style for section=%s from=%s to=%s based on backend canonical map",
                section_type,
                section.get("style"),
                style,
            )
        section["type"] = section_type
        section["style"] = style
        section["is_hidden"] = bool(section.get("is_hidden", False))


def _apply_patches_to_layout(
    content: list[dict[str, Any]],
    patches: list[PatchCommand],
) -> list[dict[str, Any]]:
    layout = [deepcopy(s) for s in content if isinstance(s, dict)]
    _normalize_section_styles(layout)
    for patch in patches:
        patch_type = normalize_section_type(patch.type)
        if not patch_type:
            continue
        action = patch.action
        patch_instance_key = patch.instance_key

        def _matches(s: dict[str, Any]) -> bool:
            if normalize_section_type(s.get("type")) != patch_type:
                return False
            if patch_instance_key:
                return s.get("instance_key") == patch_instance_key
            return True

        if action == "delete_block":
            layout = [s for s in layout if not _matches(s)]
            continue
        if action == "add_block":
            new_section: dict[str, Any] = {"type": patch_type, **deepcopy(patch.updates)}
            if patch_instance_key:
                new_section["instance_key"] = patch_instance_key
            layout.append(new_section)
            _normalize_section_styles(layout[-1:])
            continue
        if action == "update_block":
            target = next((s for s in layout if _matches(s)), None)
            if target is None:
                target = {"type": patch_type}
                if patch_instance_key:
                    target["instance_key"] = patch_instance_key
                layout.append(target)
            target.update(deepcopy(patch.updates))
            _normalize_section_styles([target])
    return layout


def _derive_final_layout(
    blueprint: PageBlueprint | None,
    patches: list[PatchCommand] | None,
    page_context_obj: dict[str, Any] | None,
) -> list[dict[str, Any]] | None:
    if blueprint is not None:
        content = blueprint.model_dump().get("content", [])
        if isinstance(content, list):
            layout = [s for s in content if isinstance(s, dict)]
            _normalize_section_styles(layout)
            return layout
        return None
    if not patches:
        return None
    if not isinstance(page_context_obj, dict):
        return None
    existing = page_context_obj.get("content")
    if not isinstance(existing, list):
        return None
    return _apply_patches_to_layout(existing, patches)


def _validate_ai_uploads_against_layout(raw_uploads: Any, final_layout: list[dict[str, Any]] | None) -> None:
    if not isinstance(raw_uploads, list) or final_layout is None:
        return
    rendered_slots = {
        (
            slot["section"],
            slot["field"],
            slot.get("index"),
        )
        for slot in collect_rendered_upload_slots(final_layout)
    }
    for raw in raw_uploads:
        if not isinstance(raw, dict):
            logger.warning("Rejected uploads_needed entry with invalid shape: %s", raw)
            continue
        raw_index = raw.get("index")
        if raw_index is not None:
            try:
                raw_index = int(raw_index)
            except (TypeError, ValueError):
                raw_index = None
        slot_key = (str(raw.get("section", "")).lower(), str(raw.get("field", "")), raw_index)
        if slot_key not in rendered_slots:
            logger.warning("Rejected non-rendered uploads_needed entry from AI: %s", raw)


def _validate_styles_selected(raw: Any) -> list[StyleSelection]:
    """The model's own styles_selected, each style checked against the catalog.
    Entries for unknown sections or with a broken shape are dropped; an invalid
    style becomes the section's first catalog style."""
    if not isinstance(raw, list):
        if raw is not None:
            logger.warning("Ignored styles_selected that is not a list: %.120r", raw)
        return []
    selections: list[StyleSelection] = []
    for entry in raw:
        if not isinstance(entry, dict):
            logger.warning("Dropped non-object styles_selected entry: %.120r", entry)
            continue
        section_type = normalize_section_type(entry.get("section"))
        if section_type not in catalog.GENERATABLE_SECTIONS:
            logger.warning("Dropped styles_selected entry for unsupported section %r", entry.get("section"))
            continue
        style, changed = normalize_style(section_type, entry.get("style"), entry.get("section_subtype"))
        if changed:
            logger.warning(
                "Adjusted invalid styles_selected style for section=%s from=%s to=%s",
                section_type, entry.get("style"), style,
            )
        try:
            selections.append(StyleSelection(**{**entry, "style": style}))
        except Exception as e:
            logger.warning("Dropped malformed styles_selected entry %.120r: %s", entry, e)
    return selections


def _code_block_adds_to_sections(
    raw_code_blocks: Any,
    raw_blueprint: Any,
    raw_patches: Any,
) -> tuple[Any, Any]:
    """Each code_blocks "add" becomes a Custom Code section: in a full page,
    right after the section it was meant for; otherwise an add_block patch.
    Returns the remaining code_blocks and the patches."""
    if not isinstance(raw_code_blocks, list):
        return raw_code_blocks, raw_patches
    adds = [b for b in raw_code_blocks if isinstance(b, dict) and b.get("action") == "add"]
    if not adds:
        return raw_code_blocks, raw_patches
    rest = [b for b in raw_code_blocks if not any(b is a for a in adds)]
    content = raw_blueprint.get("content") if isinstance(raw_blueprint, dict) else None
    for block in adds:
        section = {"type": catalog.CODE_SECTION_TYPE, "html": block.get("html")}
        if isinstance(content, list):
            target_type = normalize_section_type(block.get("section"))
            target_key = block.get("instance_key")
            index = next(
                (i + 1 for i, s in enumerate(content)
                 if isinstance(s, dict) and target_type and normalize_section_type(s.get("type")) == target_type
                 and (not target_key or s.get("instance_key") == target_key)),
                len(content),
            )
            content.insert(index, section)
        else:
            raw_patches = [*(raw_patches if isinstance(raw_patches, list) else []),
                           {"action": "add_block", "type": catalog.CODE_SECTION_TYPE,
                            "updates": {"html": block.get("html")}}]
    logger.info("Turned %d code_blocks add(s) into Custom Code section(s)", len(adds))
    return rest or None, raw_patches


def _pass_code_blocks(raw: Any, page_context: str | None) -> list[dict[str, Any]] | None:
    """The model's code_blocks, passed through unchanged — the frontend applies
    and caps them (catalog `code_blocks` spec). Only non-object entries are
    dropped (they cannot be serialized); spec problems are logged, not fixed."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        logger.warning("Ignored code_blocks that is not a list: %.120r", raw)
        return None
    spec = catalog.CODE_BLOCKS_SPEC
    actions = spec.get("actions") or {}
    blocks: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            logger.warning("Dropped non-object code_blocks entry: %.120r", entry)
            continue
        action = entry.get("action")
        rules = actions.get(action)
        if rules is None:
            logger.warning("code_blocks entry with unknown action %r", action)
        else:
            missing = [f for f in rules.get("required", ()) if not entry.get(f)]
            if missing:
                logger.warning("code_blocks %s entry is missing %s", action, missing)
        html = entry.get("html")
        if isinstance(html, str) and len(html) > spec.get("html_max_chars", 20000):
            logger.warning("code_blocks html is %d chars (frontend caps it)", len(html))
        block_id = entry.get("id")
        if action in ("update", "delete") and block_id and block_id not in (page_context or ""):
            logger.warning("code_blocks %s uses id %r that is not in the page state", action, block_id)
        blocks.append(entry)
    return blocks or None


# ---------------------------------------------------------------------------
# System prompt — the frontend's tuned prompt and section registry, loaded
# from services/builder_ai/builder-ai-prompt.md (an exact copy of fe-serey-web
# docs/ai/builder-ai-prompt.md, generated by scripts/export-ai-builder-prompt.js).
# Change it on the frontend side and copy it over — never edit it here.
# _SERVICE_ADDENDUM covers what only this service knows about: the blocks it
# adds to the user message and the onboarding intake.
# ---------------------------------------------------------------------------

_SERVICE_ADDENDUM = """---

## SERVICE ADDENDUM
The AI service adds some blocks to the user message. These rules explain them; they do not change the rules above.

### Blocks the service may add
- `COMMUNITY ID:` — set `blueprint.community_id` to that integer.
- `REPLY LANGUAGE:` — write `reply` in that language, even if the user types in another one. It applies to
  `reply` only; page copy still follows the language the user writes their content in.
- `PREVIOUS PAGE STATE` — the page before your last change. When the user wants one specific old value back
  ("put the old title back", "the previous colours"), read it from there and restore exactly that value with
  `update_block` patches; for a colour theme, patch every section listed there. Never guess an old value. If
  this block is absent, say you can't see the earlier version and suggest typing "undo".
- `WHAT THE PAGE'S IMAGES ACTUALLY SHOW` — a real analysis of the uploaded images: trust it, and match each
  "Image N" to its URL. Without this block you cannot see image content — never describe or guess what a
  photo shows; ask the user to describe it instead.
- `CONVERSATION HISTORY` — earlier turns of this session.
- "(Community facts …)" at the end of the user message — what the community really has (online shop, podcast
  episodes) and whether the user uploaded photos. Follow it on every full page build, even over a fixed section
  list: product section only with a shop (and always with one), PODCAST when there are episodes, no photo gallery
  without photos.

### Custom Code sections (type 11, key `code`) — instead of code blocks
This overrides the "Code / HTML blocks" part above and the rule against sending type 11. When you write HTML
for the page, put it in a Custom Code section: a full-width section in the page flow, rendered in a sandboxed
iframe (extra copies have keys like `code__2`).
- Never add code blocks: no `code_blocks` "add". You may still update or delete a code block already listed in
  "CODE / HTML BLOCKS ON THE PAGE".
- Full page: put `{ "type": 11, "html": "...", "colors": { "bg": "<hex>" } }` in `content`, right after the
  section it relates to. Edit turn: an `add_block` patch with `"type": 11` and `updates` `{ "html": "...",
  "colors": { "bg": "<hex>" } }`.
- Content: real content about THIS page — built from the brand, products, services and description in the
  page state and the user's message (what it is, how it works, what makes it different). Never generic filler,
  never invented facts (no prices, times, dates, numbers, reviews or names the user did not give).
- Colours: `colors.bg` is a background the page already uses (a section bg or its tint from the theme), not a
  new colour, and it differs from the sections next to it. Keep the html background transparent so the
  section bg shows. The service adds the colours of the background the section lands on as CSS variables —
  use them for every colour in your CSS: `var(--page-text)`, `var(--page-muted)`, `var(--page-accent)`,
  `var(--page-card)` (cards and panels) and `var(--page-line)` (borders), never fixed text colours, so the
  section reads on a light or a dark background. Use the page's fonts.
- Interactive and animated is welcome — a wheel or dial that shows details per segment, tabs, an accordion,
  flip cards, a stepper — when it works: every clickable part must visibly change something inside the section
  through an inline `<script>` (`addEventListener`). Add a subtle entrance animation and smooth hover/active
  transitions, turned off under `@media (prefers-reduced-motion: reduce)`.
- Nothing that leads nowhere: no links (unless to a URL the user gave), forms, inputs, or buttons, pills, tabs
  or filter bars without a script that makes them work, and no external scripts. Such a section is removed.
- No AI look: no emoji (not even as icons — draw icons with CSS or inline SVG in the accent colour), no
  gradients (flat palette colours only, also for text), no pill badges, and no mention of AI. A small
  uppercase label above a heading is fine.
- Height: the section grows to fit its content, so let the content set the height. Never use `vh` heights,
  a fixed height on the outer wrapper, or `position: fixed` — they cut the bottom off. Absolute
  positioning only inside an element with its own fixed size (for example the segments of a 360px wheel).
- Balanced spacing: one outer wrapper, centred, `max-width` about 1100px, with the same padding top and bottom
  (about 64px, 40px on phones) and 24px at the sides. Use one spacing scale (8, 16, 24, 32, 48px): equal gaps
  between items, the same inner padding in every card, cards in a row the same height, and text aligned the
  same way throughout. No empty space at the top or bottom.
- One self-contained snippet: CSS in an inline `<style>`, no `<html>`/`<head>`/`<body>` tags, no markdown
  fences, responsive (`max-width: 100%`, items stack on phones), under 50,000 characters. Only uploaded image
  URLs; embed only URLs the user gave you.
- A type 11 section already on the page may be the user's own code. Change its html (`update_block` with
  `instance_key` and `html`) or delete it only when the user asks for that section. On a full page build, the
  service keeps the page's existing type 11 sections where they were; to move one, add
  `{ "type": 11, "instance_key": "<its key>" }` (no html) at the new place. A type 11 section without `html`
  is legacy data from an older section; leave it alone.

### Guided onboarding intake
When the message starts with "You are building a landing page in a guided multi-step flow." and contains
"Current phase: final", it is the last step of the onboarding wizard, with all of the user's answers:
- Send a full blueprint, never patches. If it has a "Task: ... exactly N sections in this order: ..." line,
  use exactly those sections in that order — nothing added, nothing removed.
- "Brand name:" → the basis of the hero title (the copy rules above still apply).
- "Platform details:" → the source for ABOUT and every description. Use the user's facts; do not invent another story.
- "Product N: <name> — <description> [image: <url>]" lines: when at least one has an [image: ...], the page's
  GALLERY is a PHOTO gallery — always send `section_subtype: "gallery"` on it. If the community facts say there is
  an online shop, keep a product section too (photo gallery `instance_key: "gallery"`, product section
  `"gallery__2"`). Make exactly one `images[]` item per Product line, in the same order: `image_url`
  = that line's exact [image: ...] URL ("" when it has none), `name` = its title, `description` = its
  description (write a short one if it is empty). Never add, drop or reorder items, and add no second photo
  gallery. Without any [image: ...], there is no photo gallery (see the community facts).
- "Contact information:" → FOOTER `email` / `phone` / `location` / `social_links`. When it is missing or empty
  (the wizard may not ask for it), leave those fields out — never invent them — and say in `reply` that the
  user can add their contact details. "Logo: <url>" → FOOTER `logo_url` only.
- "Banner images:" URLs → HERO `image_url`. "Additional images:" URLs → image fields the chosen layouts show.
- "Additional section content provided by user:" lines (TESTIMONIALS:, FAQ:, TEAM:, VISION:, SUBSCRIPTION:,
  RANKING:) → that section's items or copy, used as written (grammar polish only). Testimonials the user gave
  are real: do not mark them "Sample review".
- Also return a top-level `"image_prompts": {"hero": "...", "about": "..."}`: one or two English sentences
  each, describing a photo of THIS business (its place, craft, products or atmosphere — hands, objects and
  places, never faces, text, signs, labels or logos — describe a scene with no writing in it). Send
  `image_prompts` only on this final intake.
"""


def _build_system_prompt() -> str:
    return f"{catalog.builder_prompt_from_doc()}\n\n{_SERVICE_ADDENDUM}"


BUILDER_SYSTEM_PROMPT = _build_system_prompt()


@router.post("/builder/chat", response_model=BuilderChatResponse, dependencies=[Depends(require_serey_origin), Depends(_verify_api_key)])
async def builder_chat(request: BuilderChatRequest):
    logger.info("Model: %s | user=%s session=%s community=%s", grok.BUILDER_MODEL, request.user_id, request.session_id, request.community_id)
    # Resolved before the no-model revert path so its canned reply is localized too.
    reply_language = _resolve_reply_language(request)

    # 0. Full-undo requests are deterministic — no model call. The frontend keeps
    # the real page history; revert=True tells it to restore its last snapshot.
    # Same for color-restore requests when the LAST change was colors-only:
    # undoing that whole turn restores every section's colors exactly.
    wants_old_colors = (
        bool(_EXPLICIT_RESTORE_RE.search(request.message or ""))
        and not _PARTIAL_QUALIFIER_RE.search(request.message or "")
        and bool(_COLOR_INTENT_RE.search(request.message or ""))
        and _last_change_was_color_only(request.session_id)
    )
    if request.page_context and (_is_full_undo(request.message) or wants_old_colors):
        logger.info("Full-undo intent detected — returning revert=True without model call")
        reply = _revert_reply(request.message, reply_language)
        try:
            append_session_turn(
                session_id=request.session_id,
                user_message=request.message,
                assistant_reply=reply + " [reverted to previous snapshot]",
            )
        except Exception as e:
            logger.warning("Failed to save revert turn: %s", str(e))
        return BuilderChatResponse(
            reply=reply,
            revert=True,
            # No model was called, so this turn is free.
            usage=BuilderUsage(outcome="revert", vision_used=False),
            user_id=request.user_id,
            session_id=request.session_id,
        )

    # 1. Retrieve session history
    session_history = get_session_history_prompt(request.session_id)
    history_section = (
        f"CONVERSATION HISTORY (this session):\n{session_history}"
        if session_history
        else "CONVERSATION HISTORY: (no prior turns in this session)"
    )

    # 2. Build the full prompt
    community_ctx = (
        f"COMMUNITY ID: {request.community_id} — you MUST use this exact integer in blueprint.community_id"
        if request.community_id
        else "COMMUNITY ID: not provided — use 0 as a placeholder"
    )

    page_ctx = (
        f"== CURRENT PAGE STATE (sent by frontend) ==\n{request.page_context}"
        if request.page_context
        else "== CURRENT PAGE STATE: (no page context provided) =="
    )
    page_context_obj = _parse_page_context_json(request.page_context)
    frontend_style_map = parse_frontend_style_map(page_context_obj)
    if frontend_style_map:
        for mismatch in compare_with_backend_map(frontend_style_map):
            logger.warning("Frontend style map mismatch: %s", mismatch)

    # On undo-ish requests, show the AI the page state from the previous turn so
    # it can restore specific old values via update_block patches.
    prev_state_section = ""
    if _has_undo_intent(request.message):
        prev_ctx = _get_prev_page_context(request.session_id)
        if prev_ctx and prev_ctx != (request.page_context or ""):
            prev_state_section = (
                "\n== PREVIOUS PAGE STATE (before your last change — use this to restore "
                f"the specific values the user wants back, via update_block patches) ==\n{prev_ctx}\n"
            )

    # When the user asks about images, look at them with the vision model first
    # ...and look up what the community has (shop, podcast) at the same time.
    (vision_section, vision_used), community_facts = await asyncio.gather(
        _vision_context(request.message, request.page_context),
        get_community_facts(request.community_id),
    )
    has_photos = _user_has_photos(request.message, request.page_context)
    full_build = _is_full_build_request(request.message)
    page_kind = _page_kind(request.message, community_facts) if full_build else "any"
    photo_urls = _user_photo_urls(request.message, request.page_context) if full_build else []
    full_build_note = (
        _full_build_note(request.session_id, page_kind, has_photos, photo_urls) if full_build else ""
    )
    if full_build:
        logger.info("Full build: page kind %s, %d user photo(s)%s", page_kind, len(photo_urls),
                    " — photo gallery" if len(photo_urls) >= _PHOTO_GALLERY_MIN else "")
    else:
        # The page state tells what kind of page this is better than a short edit request.
        edit_kind = _page_kind(f"{request.page_context or ''}\n{request.message or ''}", community_facts)
        full_build_note = _code_section_edit_note(request.message, request.session_id, edit_kind, has_photos)
        if full_build_note:
            logger.info("Edit asks for a Code section: page kind %s", edit_kind)
    build_theme = _pick_build_theme(request.session_id) if full_build and _ai_picks_colours(request.message) else None
    if build_theme:
        full_build_note += _ai_palette_note(build_theme)
        logger.info("Full build: random theme %s", build_theme["id"])
    elif full_build:
        build_theme = _chosen_theme(request.message)
        if build_theme:
            logger.info("Full build: theme from onboarding %r", build_theme["label"])
    # A whole page gets more thinking and more creative freedom; small edits
    # stay fast and predictable on the model defaults.
    model_settings: dict[str, Any] = (
        {
            "model": BUILDER_FULL_MODEL,
            "reasoning_effort": _FULL_BUILD_REASONING_EFFORT or None,
            "temperature": _FULL_BUILD_TEMPERATURE,
        }
        if full_build else {}
    )
    used_model = model_settings.get("model") or grok.BUILDER_MODEL

    full_prompt = f"""{community_ctx}

{page_ctx}
{prev_state_section}{vision_section}
{history_section}

---

{_reply_language_directive(reply_language)}USER: {request.message}{_onboarding_photo_gallery_note(request.message)}{_onboarding_contact_note(request.message)}{_community_facts_note(community_facts, has_photos)}{full_build_note}

Respond with valid JSON now:
"""

    # 3. Call Grok — re-generate once on unusable output, if the budget allows
    data = None
    # Summed across EVERY billed attempt (a failed parse still cost tokens);
    # serey-api settles credits from these.
    token_counts: dict[str, int] = grok.empty_usage()
    deadline = time.monotonic() + _BUILDER_TIME_BUDGET_S
    auto_image_slots = _auto_image_slots(request.message)
    auto_image_task = (
        asyncio.create_task(_prefetch_auto_images(request.message, deadline, auto_image_slots))
        if auto_image_slots
        else None
    )
    prompt_for_attempt = full_prompt
    def _clean_raw(raw: str) -> str:
        """Strip markdown code fences the model sometimes wraps around JSON."""
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[-1]
            if stripped.endswith("```"):
                stripped = stripped[: stripped.rfind("```")]
        return stripped.strip()

    for attempt in (1, 2):
        raw_response = ""
        remaining = deadline - time.monotonic()
        try:
            call_timeout = min(grok.BUILDER_CALL_TIMEOUT_S, remaining)
            if model_settings.get("model"):
                # Leave room for the grok-4.3 fallback below.
                call_timeout = min(call_timeout, _FULL_BUILD_CALL_TIMEOUT_S)
            raw_response, counts = await asyncio.to_thread(
                grok.generate_builder_with_usage,
                prompt_for_attempt,
                BUILDER_SYSTEM_PROMPT,
                call_timeout,
                **model_settings,
            )
            token_counts = grok.add_usage(token_counts, counts)
            cleaned = _clean_raw(raw_response)
            if not cleaned:
                raise grok.UnusableBuilderOutput("empty after fence stripping", raw_response, grok.empty_usage())
            # If model returned plain text instead of JSON, try to salvage an
            # embedded JSON envelope (models sometimes echo the reply as prose
            # BEFORE the JSON); otherwise wrap the text as a reply-only envelope.
            if not cleaned.startswith("{"):
                brace = cleaned.find("{")
                salvaged = None
                if brace != -1:
                    try:
                        # raw_decode tolerates trailing prose after the object,
                        # so "text {json} more text" still salvages the envelope.
                        candidate, _end = json.JSONDecoder().raw_decode(cleaned, brace)
                        if isinstance(candidate, dict) and "reply" in candidate:
                            salvaged = candidate
                    except json.JSONDecodeError:
                        pass
                if salvaged is not None:
                    logger.warning("Model wrapped JSON in prose — salvaged embedded envelope")
                    data = salvaged
                    break
                logger.warning("Model returned plain text instead of JSON — wrapping as reply: %s", cleaned[:200])
                data = {"reply": cleaned, "blueprint": None, "patches": None}
                break
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                # JSON followed by trailing prose ("{...} Hope that helps!")
                data, _end = json.JSONDecoder().raw_decode(cleaned)
                logger.warning("Model appended prose after JSON — ignored trailing text")
            break
        except (json.JSONDecodeError, grok.UnusableBuilderOutput) as e:
            if isinstance(e, grok.UnusableBuilderOutput):
                token_counts = grok.add_usage(token_counts, e.counts)
                raw_response = e.text or raw_response
            logger.error("Unusable builder output (attempt %d): %s | Raw: %s", attempt, str(e), raw_response[:600])
            # Only re-generate if a second full answer can still beat the proxy timeout.
            if attempt == 2 or deadline - time.monotonic() < _MIN_RETRY_BUDGET_S:
                raise HTTPException(status_code=422, detail=f"AI returned unusable output: {str(e)}")
            truncated = isinstance(e, grok.UnusableBuilderOutput) and "truncated" in e.reason
            prompt_for_attempt = full_prompt + (
                _RETRY_NOTE_TRUNCATED if truncated else _RETRY_NOTE_INVALID_JSON
            )
        except grok.APITimeoutError as e:
            # The full-build model can get slow under load (grok-4.7 passed 90s
            # with 4 builds at once). Build the page on the fast edit model
            # instead of failing the turn — a plainer page beats an error.
            if model_settings.get("model") and deadline - time.monotonic() >= _MIN_FALLBACK_BUDGET_S:
                logger.warning(
                    "Full build on %s timed out after %.0fs — retrying on %s",
                    used_model, call_timeout, grok.BUILDER_MODEL,
                )
                model_settings = {"temperature": _FULL_BUILD_TEMPERATURE}
                used_model = grok.BUILDER_MODEL
                continue
            logger.error("Grok timeout (attempt %d): %s", attempt, str(e))
            raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")
        except Exception as e:
            # Transient API errors were already retried inside grok; retrying
            # here again would only stack timeouts past the proxy budget.
            logger.error("Grok error (attempt %d): %s", attempt, str(e))
            raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")
    if data is None:
        raise HTTPException(status_code=502, detail="AI service returned no data")
    assert isinstance(data, dict)  # type: narrowing for static analysis

    # 3b. Quality check for a full page: send the model back once with the exact
    # problems (invented facts, thin FAQ, filler, …) if the time budget allows,
    # and keep whichever answer has fewer problems. Never fails the turn.
    if data.get("blueprint"):
        quality_known = (request.page_context or "") + "\n" + (request.message or "")
        problems = _quality_problems(data, quality_known, request.message, build_theme is not None)
        if problems:
            logger.warning("Quality check: %d problem(s) in the page: %s", len(problems), "; ".join(problems))
            if deadline - time.monotonic() >= _MIN_QUALITY_RETRY_BUDGET_S:
                try:
                    raw_retry, retry_counts = await asyncio.to_thread(
                        grok.generate_builder_with_usage,
                        full_prompt + _quality_retry_note(problems),
                        BUILDER_SYSTEM_PROMPT,
                        min(grok.BUILDER_CALL_TIMEOUT_S, deadline - time.monotonic()),
                        # Same settings as the first try: grok-4.7 must keep its
                        # low effort, its default thinks for ~3 minutes.
                        **model_settings,
                    )
                    token_counts = grok.add_usage(token_counts, retry_counts)
                    retry_data = _parse_model_json(raw_retry)
                    if retry_data and retry_data.get("blueprint"):
                        retry_problems = _quality_problems(retry_data, quality_known, request.message, build_theme is not None)
                        logger.info("Quality check: retry has %d problem(s) (was %d)", len(retry_problems), len(problems))
                        if len(retry_problems) < len(problems):
                            data = retry_data
                except grok.UnusableBuilderOutput as e:
                    token_counts = grok.add_usage(token_counts, e.counts)
                    logger.warning("Quality retry unusable (%s) — keeping the first page", e.reason)
                except Exception as e:
                    logger.warning("Quality retry failed (%s) — keeping the first page", e)
            else:
                logger.info("Quality check: no time left for a retry — keeping the first page")
    # 4. Extract envelope fields
    _VALID_ANIMATIONS = set(catalog.ANIMATION_STYLES)
    try:
        reply: str = data.get("reply") or ""
        raw_blueprint = data.get("blueprint")
        raw_patches = data.get("patches")
        raw_uploads = data.get("uploads_needed")
        raw_styles_selected = data.get("styles_selected")
        raw_code_blocks = data.get("code_blocks")
        model_revert = data.get("revert") is True
        raw_animation = data.get("animation_style")
        animation_style: str | None = (
            raw_animation if isinstance(raw_animation, str) and raw_animation in _VALID_ANIMATIONS else None
        )
    except AttributeError as e:
        logger.error("Envelope extract error: %s | Data: %s", str(e), data)
        raise HTTPException(status_code=422, detail=f"AI returned unexpected format: {str(e)}")
    # The contract is blueprint OR patches. A full page already contains every
    # change, so the blueprint wins.
    if raw_blueprint and raw_patches:
        logger.warning("Model sent both blueprint and patches — dropped the %d patch(es)",
                       len(raw_patches) if isinstance(raw_patches, list) else 0)
        raw_patches = None
    # Bob writes HTML as Custom Code sections, not floating code blocks: turn
    # any code_blocks "add" into one (update/delete of existing blocks pass).
    raw_code_blocks, raw_patches = _code_block_adds_to_sections(raw_code_blocks, raw_blueprint, raw_patches)

    def _normalize_blueprint(raw: dict) -> dict:
        """Fix common AI field name mismatches before Pydantic validation."""
        # Clamp animation_style to known values
        anim = str(raw.get("animation_style") or "fade").lower()
        raw["animation_style"] = anim if anim in _VALID_ANIMATIONS else "fade"
        raw.setdefault("template", 1)
        # The model sometimes omits it; the request always knows the community
        if raw.get("community_id") in (None, ""):
            raw["community_id"] = request.community_id
        raw.setdefault("font", "")
        # Fonts must come from the frontend whitelist; unknown fonts fall back to system default
        if raw.get("font") and raw["font"] not in catalog.FONT_OPTIONS:
            logger.warning("Dropped unknown font from AI blueprint: %s", raw["font"])
            raw["font"] = ""

        page_context_text = request.page_context or ""
        # Text the AI may legitimately echo URLs/scripts from: the page it was shown
        # and what the user typed. Anything else is invented and gets scrubbed.
        known_text = page_context_text + "\n" + (request.message or "")

        content = raw.get("content")
        raw["content"] = [s for s in content if isinstance(s, dict)] if isinstance(content, list) else []

        for section in raw["content"]:
            section_type = normalize_section_type(section.get("type"))
            if section_type:
                section["type"] = section_type
            # Subtype first: it decides which style list (photo or product) applies.
            if section_type == "GALLERY":
                if section.get("section_subtype") not in (None, "", *catalog.GALLERY_SUBTYPES):
                    section["section_subtype"] = "product"
            style, style_changed = normalize_style(section_type, section.get("style"), section.get("section_subtype"))
            if style_changed:
                logger.warning(
                    "Adjusted invalid blueprint style for section=%s from=%s to=%s based on backend canonical map",
                    section_type,
                    section.get("style"),
                    style,
                )
            section["style"] = style
            # bg_image_url is user-uploaded, never AI-generated. Keep it only when the AI
            # echoed a real URL that already appears in the page context; otherwise clear it.
            bg_url = section.get("bg_image_url")
            if not (isinstance(bg_url, str) and bg_url.startswith("http") and bg_url in page_context_text):
                section["bg_image_url"] = ""
            section.setdefault("bg_image_opacity", 0.5)
            # Clamp new enum-ish fields to values the frontend renders
            if section.get("section_theme") not in catalog.SECTION_THEMES:
                section["section_theme"] = ""
            if section.get("image_shape") and section["image_shape"] not in catalog.IMAGE_SHAPES:
                section["image_shape"] = ""
            if section_type in ("BLOG", "NOTES") and section.get("feed_type"):
                feed = str(section["feed_type"]).lower()
                section["feed_type"] = "latest" if feed in ("new", "latest") else "trending"
            # Editor-managed features the AI must never author
            for editor_field in ("floating_widgets", "mobile_overrides", "tablet_overrides", "text_offsets"):
                section.pop(editor_field, None)
            # Gallery images: normalize field names + ensure name/description exist
            for img in section.get("images", []) or []:
                if "url" in img and "image_url" not in img:
                    img["image_url"] = img.pop("url")
                if "title" in img and "name" not in img:
                    img["name"] = img.pop("title")
                url = img.get("image_url", "")
                if url and not url.startswith("http"):
                    img["image_url"] = ""
                img.setdefault("name", "")
                img.setdefault("description", "")
            # FAQ: normalize q/a → question/answer
            for item in section.get("faq_items", []) or []:
                if "q" in item and "question" not in item:
                    item["question"] = item.pop("q")
                if "a" in item and "answer" not in item:
                    item["answer"] = item.pop("a")
            # Testimonials: normalize quote → content
            for item in section.get("testimonial_items", []) or []:
                if "quote" in item and "content" not in item:
                    item["content"] = item.pop("quote")
            # Footer social_links: {platform} → {type}
            for link in section.get("social_links", []) or []:
                if "platform" in link and "type" not in link:
                    link["type"] = link.pop("platform")
        _ensure_onboarding_photo_gallery(raw["content"], request.message, community_facts.get("has_shop"))
        _apply_community_facts(raw["content"], community_facts, has_photos)
        # Structure + safety pass: known types, one HERO/FOOTER (first/last),
        # unique instance keys, no invented image URLs or embed scripts. The
        # page's Custom Code sections come back unchanged.
        page_content = (page_context_obj or {}).get("content")
        raw["content"] = sanitize_content(raw["content"], known_text, page_content)
        # Colour rules: Bob's Code sections use a background of the page's
        # palette, and two sections next to each other never share one.
        owned = page_code_keys(page_content)
        if build_theme:
            _apply_build_theme(raw["content"], build_theme, owned)
        else:
            apply_theme_to_code_sections(raw["content"], owned)
        separate_adjacent_backgrounds(raw["content"], owned)
        inject_code_theme_vars(raw["content"], owned)
        return raw

    # 5. Validate blueprint (if present)
    blueprint = None
    generated_images: list[GeneratedImage] = []
    if raw_blueprint:
        try:
            normalized_blueprint = _normalize_blueprint(raw_blueprint)
            # First build without any user images: generate the hero/about photos.
            if auto_image_slots:
                prefetched_images = await auto_image_task if auto_image_task else None
                generated_images = await _auto_fill_key_images(
                    normalized_blueprint,
                    data.get("image_prompts"),
                    deadline,
                    prefetched_images,
                    auto_image_slots,
                )
            blueprint = PageBlueprint(**normalized_blueprint)
        except Exception as e:
            logger.error("Blueprint validation failed: %s | Data: %s", str(e), raw_blueprint)
            raise HTTPException(
                status_code=422,
                detail=f"AI returned invalid blueprint structure: {str(e)}",
            )

    # 6. Validate patches (if present)
    patches = None
    normalized_patch_dicts: list[dict[str, Any]] = []
    color_only_request = _is_color_only_request(request.message)
    if raw_patches and isinstance(raw_patches, list):
        try:
            normalized = []
            known_types = existing_section_types((page_context_obj or {}).get("content"))
            patch_known_text = (request.page_context or "") + "\n" + (request.message or "")
            for p in raw_patches:
                if not isinstance(p, dict):
                    logger.warning("Dropped non-object patch entry: %.120r", p)
                    continue
                # AI sometimes uses { action, block/new_block: {type, ...} } instead of { action, type, updates }
                raw_block = p.get("block") or p.get("new_block")
                if raw_block and "type" not in p:
                    p = {
                        "action": p.get("action"),
                        "type": raw_block.get("type", ""),
                        "updates": {k: v for k, v in raw_block.items() if k != "type"},
                    }
                patch_type = normalize_section_type(p.get("type"))
                p["type"] = patch_type
                updates = p.get("updates")
                if not isinstance(updates, dict):
                    updates = {}
                    p["updates"] = updates
                for editor_field in ("floating_widgets", "mobile_overrides", "tablet_overrides", "text_offsets"):
                    updates.pop(editor_field, None)
                # Color-only request: never let layout/appearance changes ride
                # along (rule 17 forbids more than just "style").
                if color_only_request and p.get("action") == "update_block":
                    for banned in ("style", "image_shape", "section_theme", "section_height"):
                        if banned in updates:
                            logger.warning("Stripped %s=%s from update_block on color-only request", banned, updates[banned])
                            updates.pop(banned, None)
                # Same item-key compat fixes as blueprints (patches previously
                # passed q/a/quote/platform/title through to the frontend raw)
                for item in updates.get("faq_items") or []:
                    if isinstance(item, dict):
                        if "q" in item and "question" not in item:
                            item["question"] = item.pop("q")
                        if "a" in item and "answer" not in item:
                            item["answer"] = item.pop("a")
                for item in updates.get("testimonial_items") or []:
                    if isinstance(item, dict) and "quote" in item and "content" not in item:
                        item["content"] = item.pop("quote")
                for link in updates.get("social_links") or []:
                    if isinstance(link, dict) and "platform" in link and "type" not in link:
                        link["type"] = link.pop("platform")
                for img in updates.get("images") or []:
                    if isinstance(img, dict) and "title" in img and "name" not in img:
                        img["name"] = img.pop("title")
                # The frontend displays a member's `bio` (blueprints get the same
                # copy in schemas.blueprint.TeamMember).
                for member in updates.get("members") or []:
                    if isinstance(member, dict) and member.get("description") and not member.get("bio"):
                        member["bio"] = member["description"]
                if patch_type:
                    # Canonical backend map always wins for style IDs.
                    if "style" in updates:
                        normalized_style, style_changed = normalize_style(
                            patch_type, updates.get("style"), updates.get("section_subtype")
                        )
                        if style_changed:
                            logger.warning(
                                "Adjusted invalid patch style for section=%s from=%s to=%s based on backend canonical map",
                                patch_type,
                                updates.get("style"),
                                normalized_style,
                            )
                        updates["style"] = normalized_style
                p = sanitize_patch(p, known_types, patch_known_text)
                if p is not None:
                    normalized.append(p)
            normalized_patch_dicts = normalized
            # Every patch dropped by validation -> no patches at all (None, not [])
            patches = [PatchCommand(**p) for p in normalized_patch_dicts] or None
        except Exception as e:
            logger.error("Patches validation failed: %s | Data: %s", str(e), raw_patches)
            raise HTTPException(
                status_code=422,
                detail=f"AI returned invalid patch structure: {str(e)}",
            )

    # Safety net: the user asked to undo but the model produced no change at all —
    # fall back to a frontend snapshot revert (the frontend keeps real history)
    # instead of letting the model claim it "can't see the previous version".
    revert_fallback = False
    # Explicit restore intent: "undo"/"revert", or "old/previous/earlier … back"
    # phrasings ("i want the old color theme back"), or a full-undo phrase.
    _msg = request.message or ""
    # Whole-page revert only for unqualified restore requests; a named target
    # ("restore my old logo") without patches should surface the model's reply
    # (usually a clarifying question), not silently roll the page back.
    explicit_undo = (
        bool(_EXPLICIT_RESTORE_RE.search(_msg)) and not _PARTIAL_QUALIFIER_RE.search(_msg)
    ) or _is_full_undo(_msg)
    # Custom HTML blocks ride along with any other change (not part of the
    # blueprint-OR-patches rule) and count as a page change below.
    code_blocks = _pass_code_blocks(raw_code_blocks, request.page_context)
    if request.page_context and explicit_undo and blueprint is None and not patches and not code_blocks:
        logger.warning("Undo intent produced no patches — falling back to revert=True")
        revert_fallback = True
        reply = _revert_reply(_msg, reply_language, apologetic=False)

    final_layout = _derive_final_layout(blueprint, patches, page_context_obj)
    # The model's own layout picks, validated — never rebuilt from the layout.
    styles_selected = _validate_styles_selected(raw_styles_selected)
    if styles_selected and color_only_request:
        # Same guard as the patches above: a colour request never changes layouts.
        logger.warning("Dropped %d styles_selected entries on color-only request", len(styles_selected))
        styles_selected = []
    # A first-build image may have switched its section to an image layout;
    # a styles_selected entry for that section must not switch it back.
    for image in generated_images:
        for selection in styles_selected:
            if (
                normalize_section_type(selection.section) == normalize_section_type(image.section)
                and (selection.instance_key or None) in (None, image.instance_key)
            ):
                selection.style = image.style
    _validate_ai_uploads_against_layout(raw_uploads, final_layout)
    uploads_needed = None
    if final_layout is not None:
        uploads_needed = [UploadNeeded(**u) for u in derive_uploads_needed(final_layout)]
    elif raw_uploads and isinstance(raw_uploads, list):
        # Patch-only turn with prose page_context: there is no layout to derive
        # uploads from, so pass through the model's own upload requests. Validate
        # per entry — one malformed entry must not fail the whole request.
        echoed = []
        for u in raw_uploads:
            try:
                echoed.append(UploadNeeded(**u))
            except Exception:
                logger.warning("Dropping malformed uploads_needed entry from model: %s", u)
        uploads_needed = echoed or None

    # 7. Remember this turn's incoming page state for future undo requests.
    # Only turns that changed the page overwrite the stored snapshot, so a
    # follow-up question doesn't erase the pre-change state.
    if blueprint is not None or patches or code_blocks:
        _store_prev_page_context(request.session_id, request.page_context)
        changed_colors_only = bool(patches) and blueprint is None and not code_blocks and (
            color_only_request
            or all(p.action == "update_block" and set(p.updates.keys()) <= {"colors"} for p in patches)
        )
        _set_last_change_color_only(request.session_id, changed_colors_only)

    # 8. Save this turn to session history (non-critical)
    try:
        saved_reply = reply
        if blueprint is not None:
            section_types = [s.type for s in blueprint.content]
            saved_reply += f"\n[Generated blueprint with sections: {section_types}]"
        elif patches:
            saved_reply += f"\n[Applied {len(patches)} targeted updates]"
        if code_blocks:
            saved_reply += "\n[Code blocks: " + ", ".join(
                f"{b.get('action')} {b.get('id') or b.get('section') or ''}".strip() for b in code_blocks
            ) + "]"
        append_session_turn(
            session_id=request.session_id,
            user_message=request.message,
            assistant_reply=saved_reply,
        )
    except Exception as e:
        logger.warning("Failed to save builder_chat memory: %s", str(e))

    # What this turn produced, which is what it costs. A blueprint is a whole
    # page and prices accordingly; patches and plain replies are one credit.
    # The model may ask for a revert itself ("revert": true); the regex
    # paths above still catch the common phrasings without it.
    revert = revert_fallback or model_revert
    if blueprint is not None:
        outcome = "blueprint"
    elif patches or code_blocks:
        # A code-block change is a focused page change, priced like patches.
        outcome = "patches"
    elif revert:
        outcome = "revert"
    else:
        outcome = "reply"

    return BuilderChatResponse(
        reply=reply,
        revert=revert,
        animation_style=animation_style,
        usage=BuilderUsage(
            outcome=outcome,
            vision_used=vision_used,
            model=used_model,
            images_generated=len(generated_images),
            **token_counts,
        ),
        blueprint=blueprint,
        patches=patches,
        uploads_needed=uploads_needed,
        styles_selected=styles_selected,
        code_blocks=code_blocks,
        generated_images=generated_images or None,
        user_id=request.user_id,
        session_id=request.session_id,
    )
