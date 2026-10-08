# POST /api/builder/chat — Conversational AI page builder for Serey V2 landing pages.
# The user describes or iterates on a page in plain language.
# The AI responds with a text reply AND an updated PageBlueprint (or null if not applicable).
# The blueprint matches the V2 API contract: { community_id, content: [...sections] }

import asyncio
from copy import deepcopy
from fastapi import APIRouter, HTTPException, Header, Depends
from services.security import require_serey_origin
from schemas.chat import (
    BuilderChatRequest, ChatRequest, BuilderChatResponse, BuilderUsage, GeneratedImage, UploadNeeded,
)
from schemas.blueprint import PageBlueprint, PatchCommand
from services import grok
from services import image_gen
from services import design_guidelines as design
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
from services.blueprint_validator import existing_section_types, sanitize_content, sanitize_patch
from services.memory import append_session_turn, get_session_history_prompt
import json
import logging
import os
import re
import time
from typing import Any

router = APIRouter()
logger = logging.getLogger(__name__)

_CHAT_API_KEY = os.getenv("CHAT_API_KEY", "")

# serey-api's builder proxy aborts after 120s (BUILDER_TIMEOUT_MS); anything we
# generate after that is billed by xAI and thrown away. Keep a margin under it.
_BUILDER_TIME_BUDGET_S = float(os.getenv("BUILDER_TIME_BUDGET_S", "110"))
# A re-generation is only attempted if at least this much budget is left.
_MIN_RETRY_BUDGET_S = 30.0
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
    r"|vision|video|blog|ranking|subscription|newsletter|custom|map|countdown"
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


def _requested_language(message: str) -> str | None:
    """'en' / 'nl' when the message explicitly asks Bob to switch language."""
    if not message:
        return None
    wants_en = bool(_TO_ENGLISH_RE.search(message))
    wants_nl = bool(_TO_DUTCH_RE.search(message))
    if wants_en == wants_nl:  # neither, or ambiguous ("translate English to Dutch")
        return None
    return "en" if wants_en else "nl"


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
# First-build image fill — when the onboarding intake arrives with NO user
# images, the hero and about photos are generated (services/image_gen.py) so
# the page keeps the template's image layouts instead of text-only fallbacks.
# Only the key slots, only once: everything else stays upload / ask-first.
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


def _wants_auto_images(message: str) -> bool:
    message = message or ""
    if not (_AUTO_IMAGES_ENABLED and _ONBOARDING_FINAL_RE.search(message)):
        return False
    if _user_uploaded_photos(message):
        logger.info("First-build images skipped: the user uploaded photos during onboarding")
        return False
    return True


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
) -> list[GeneratedImage]:
    """Generate the empty hero/about photos in parallel and place them in the
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


async def _prefetch_auto_images(message: str, deadline: float) -> dict[str, str]:
    """Generate first-build images alongside the slower blueprint model call."""
    context = " ".join((message or "").split())[:1400]
    prompts = {
        "HERO": (
            f"Clean wide editorial hero background photograph, image-only, for the business "
            f"described here: {context}. Show only the real-world products, materials, setting, "
            "and atmosphere. Leave calm visual space for website copy to be overlaid separately. "
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
        style, changed = normalize_style(section_type, section.get("style"))
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


def _instance_key_for(section: dict[str, Any]) -> str:
    """Return instance_key if set, else fall back to section type string."""
    return section.get("instance_key") or normalize_section_type(section.get("type"))


def _extract_style_reasons(raw_blueprint: Any, raw_patches: Any) -> dict[str, str]:
    reasons: dict[str, str] = {}
    if isinstance(raw_blueprint, dict):
        for section in raw_blueprint.get("content", []) or []:
            if not isinstance(section, dict):
                continue
            reason = section.get("style_reason")
            key = _instance_key_for(section)
            if key and isinstance(reason, str) and reason.strip():
                reasons[key] = reason.strip()
    if isinstance(raw_patches, list):
        for patch in raw_patches:
            if not isinstance(patch, dict):
                continue
            section_type = normalize_section_type(patch.get("type"))
            key = patch.get("instance_key") or section_type
            top_reason = patch.get("style_reason")
            if key and isinstance(top_reason, str) and top_reason.strip():
                reasons[key] = top_reason.strip()
            updates = patch.get("updates")
            if not isinstance(updates, dict):
                continue
            reason = updates.get("style_reason")
            if key and isinstance(reason, str) and reason.strip():
                reasons[key] = reason.strip()
    return reasons


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


def _styles_selected_from_layout(
    final_layout: list[dict[str, Any]] | None,
    style_reasons: dict[str, str],
) -> list[dict[str, Any]] | None:
    if final_layout is None:
        return None
    styles_selected: list[dict[str, Any]] = []
    for section in final_layout:
        section_type = normalize_section_type(section.get("type"))
        if not section_type:
            continue
        instance_key = section.get("instance_key") or None
        reason_key = instance_key or section_type
        entry: dict[str, Any] = {
            "section": section_type.lower(),
            "style": int(section.get("style", 1)),
            "is_hidden": bool(section.get("is_hidden", False)),
        }
        if instance_key:
            entry["instance_key"] = instance_key
        reason = style_reasons.get(reason_key)
        if reason:
            entry["style_reason"] = reason
        styles_selected.append(entry)
    return styles_selected


# ---------------------------------------------------------------------------
# System prompt — teaches the AI the complete V2 section registry and schema.
# All catalog knowledge (types, styles, fonts, palettes, colors) is generated
# from services/section_catalog.py so the prompt can never drift from the
# validators or the frontend.
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    animation_options = " | ".join(f'"{a}"' for a in catalog.ANIMATION_STYLES)
    image_shape_options = " | ".join(catalog.IMAGE_SHAPES)
    return f"""You are an expert AI page builder for Serey community landing pages (V2).
Your job is to help users design their landing page through natural conversation.

== SECTION TYPE IDs ==
{catalog.build_type_id_block()}

== SECTION REGISTRY ==
Each page is a JSON array of section objects. Available section types (with their content fields and allowed style numbers):

{catalog.build_section_registry_block()}

FOOTER extraction rules:
  If the user's message contains a phone number, put it in the "phone" field.
  If it contains an email address, put it in the "email" field.
  If it contains Facebook/Instagram/Telegram/social links, add them to "social_links" as [{{"type":"facebook","handle":"pagename"}}].
  Never leave phone/email blank if the user provided them.
  contact_heading/social_heading are optional column headings; privacy_url/terms_url are optional legal links.

== SECTION OBJECT SHAPE ==
Every section must include:
  type              — integer type ID (string "TEXTBLOCK" for text blocks) (REQUIRED)
  style             — integer from the section's allowed style list (REQUIRED)
  is_hidden         — boolean, default false (REQUIRED)
  instance_key      — string. REQUIRED for all sections. The FIRST instance of a type uses the BARE base name (e.g. "gallery", "team", "faq" — NEVER "gallery_1"). Singletons: "hero", "footer".
  colors            — object of hex strings; allowed keys per section listed below
  bg_image_url      — always set to "" UNLESS page_context shows an ALREADY UPLOADED bg_image_url — then copy that exact URL
  bg_image_opacity  — float 0.0–1.0, default 0.5
Optional per-section fields:
  section_theme     — "" (default) or "editorial" (adds an editorial magazine treatment to the section)
  section_height    — custom height in px; omit or 0 for auto
  image_shape       — shape of the section's image: {image_shape_options} ("" = default square)
  text_styles       — typography overrides, see TYPOGRAPHY below
NEVER emit or modify: floating_widgets, mobile_overrides, tablet_overrides, text_offsets.
These are editor-managed features that exist on the page — leave them alone; the frontend preserves them.

== COLOR KEYS PER SECTION ==
{catalog.build_color_keys_block()}
  (HERO also accepts optional btn / btn_text keys for its call-to-action button.)

== COLOR DEFAULTS ==
  Light section defaults: title="#0f172a"  accent="#2b45a8"  body="#334155"  bg="#ffffff"
  Dark section defaults:  title="#eef4ff"  accent="#60a5fa"  body="#cbd5e1"  bg="#0f172a"

CURATED PALETTES — pick ONE that best fits the platform; use the EXACT hex values, and the same accent across every section:
{catalog.build_palettes_block()}
  BACKGROUNDS: hero uses hero_bg; middle sections alternate section_bg / bg_alt (always light, luminance > 0.7);
  footer bg is always dark (#0f172a or #111827 — same dark tone as hero for a bookend effect).

CRITICAL — TEXT CONTRAST RULE:
  - If a section bg is DARK (hex luminance < 0.3, e.g. #0f2044, #052e16, #1c1917, #1e1b4b):
    → ALWAYS set title="#eef4ff" or "#f0f9ff", body="#cbd5e1", subtitle="#e2e8f0"
    → NEVER use dark colors like #0f3460, #0f172a, #333, #000 for text on dark backgrounds
  - If a section bg is LIGHT (hex luminance >= 0.3, e.g. #ffffff, #f8fafc, #f0fdf4):
    → ALWAYS set title="#0f172a", body="#334155"
    → NEVER use light colors like #f0f4ff, #eef4ff for text on light backgrounds
  - Apply the correct palette-matching text colors — do not use default fallbacks when you have picked a palette
  - EXCEPTION: if the user explicitly requests a specific color, use that exact color and adjust the bg for readability.

== FONTS ==
Set the top-level blueprint "font" field to ONE font from this exact list (or "" for the system default):
{catalog.build_fonts_block()}
ALWAYS pair fonts on every full page: set blueprint "font" to the pairing's BODY font, and set the pairing's TITLE font on the hero via text_styles (e.g. {{"title_font": "Playfair Display"}}) — the frontend propagates hero fonts to all other sections automatically. A page with one font everywhere looks templated; a title/body pairing looks designed.
Curated pairings (pick the one matching the brand vibe):
{design.build_font_pairings_block()}
Script fonts (Dancing Script, Caveat, Great Vibes, Sacramento, Satisfy, Pacifico) are accent-only — never use them as the body font. Khmer-language sites must use Kantumruy Pro, Battambang, Hanuman, Siemreap, or the Noto Khmer fonts.
NEVER invent a font name that is not in the list.
Do NOT set text_styles *_size values on a full page build — the frontend has tuned responsive sizes; only set a size when the user explicitly asks for bigger/smaller text.

== TYPOGRAPHY (text_styles) ==
Each section accepts a "text_styles" object. Keys are {{slot}}{{suffix}} where slot is one of title, subtitle, description and suffix is one of _bold (bool), _italic (bool), _font (font from the list), _size (px int), _color (hex), _align ("left"|"center"|"right").
Extra slots: TESTIMONIALS supports testi_quote_*, testi_name_*, testi_role_*; GALLERY product cards support gallery_item_name_*, gallery_item_desc_*.
Use text_styles sparingly — only when the user asks for typography changes or a distinctive editorial look. Colors normally belong in "colors", not text_styles.

== STYLE DESCRIPTIONS ==

{catalog.build_style_descriptions_block()}

BACKGROUND IMAGES:
  Any section on ANY style can sit over a full-width background image — set bg_image_url + bg_image_opacity, there is no separate
  "background image" style number. Only do this when the user asks for a background-image look OR page_context shows an
  already-uploaded bg_image_url for that section; then pick a dark overlay-friendly palette with light text for that section.

== LAYOUT STYLE PREFERENCE WEIGHTS ==
When you CHOOSE or randomize a section's layout style, prefer styles by weight:
  High   — default/first choice, use most often.
  Medium — acceptable alternative, use occasionally for variety.
  Low    — only when the user explicitly asks for it, or as a last resort.
These weights break ties between styles that would both work; an explicit user request always wins, and a design
recipe's style for a section wins over the weights (the recipes are already built from High/Medium choices).

{catalog.build_style_weights_block()}

== FRONTEND STARTER TEMPLATES ==
The frontend offers 4 starter templates. Their exact structures:
{catalog.build_templates_block()}

STRUCTURE PRECEDENCE — never violate this order:
  1. If the user's message specifies an exact section list/order ("exactly N sections in this order: ..."),
     follow THAT structure precisely — same sections, same order, nothing added or removed.
  2. If page_context shows an existing page built from a template, keep its section order and only
     change what the user asked for.
  3. Only when neither applies do you choose the structure yourself (via SECTION RECOMMENDATIONS).
Design recipes below control the LOOK (palette, fonts, styles, animation) — they never add, remove,
or reorder sections when a structure is already given. When the template flow asks you to pick a
different visual identity than the template default, apply a recipe's look onto the template's structure.

EXTRA SECTIONS ON A TEMPLATE: the onboarding flow may append picked sections (TEAM, FAQ, VISION,
SUBSCRIPTION, VIDEO, BLOG...) to a template's base structure, inserted before FOOTER. Identify which
starter template the given order extends by matching its leading sections, then style each added
section to fit that template's vibe (your chosen design recipe still wins if one applies):
{catalog.build_template_extras_block()}

== GUIDED ONBOARDING INTAKE ==
When the user message starts with "You are building a landing page in a guided multi-step flow." and
contains "Current phase: final", it is the FINAL intake of the onboarding wizard — all the user's
answers in one message. Respond with a FULL blueprint (never patches), following the
"Task: ... exactly N sections in this order: ..." line per STRUCTURE PRECEDENCE rule 1.
Map the labeled intake fields to the blueprint like this:
  - "Brand name:" → basis for the hero title (copywriting rules still apply — never "Welcome to X"
    or the bare name; write an evocative title that features or evokes the brand).
  - "Platform details:" → source material for the about section and all descriptions. Use the user's
    actual facts and tone; do not invent a different story.
  - "Products / Services / Special features:" with "Product N: <name> — <description> [image: <url>]"
    lines → the GALLERY images[] items: use EVERY listed product, keep the user's exact names and
    descriptions (polish grammar only), and copy each [image: ...] URL into that item's image_url.
    Never invent extra products and never drop a listed one.
  - "Contact information:" → footer contact fields. "Logo: <url>" → footer logo_url.
  - "Banner images:" URLs → hero image_url (or bg_image_url for a background-image look).
  - "Additional images:" URLs → distribute across image slots the chosen styles actually render
    (about, gallery, team...) — use every provided image somewhere sensible if possible.
  - "Additional section content provided by user:" labeled lines map to their sections:
    TESTIMONIALS: → testimonial_items[] (parse names, roles, quotes from the text),
    FAQ: → faq_items[] ({{question, answer}}), TEAM: → members[] (names + roles),
    VISION: → the vision section's copy, SUBSCRIPTION: → the type-13 section's copy,
    RANKING: → that section. The user's real content beats anything you would write —
    use it verbatim (grammar polish only). Sections in the order list WITHOUT a labeled block get
    AI-written content per the copywriting rules.
  - IMAGE PROMPTS (final intake only): also return a top-level "image_prompts" object:
    {{"hero": "...", "about": "..."}} — one or two English sentences each describing a photo that fits
    THIS business (its real place, craft, products or atmosphere) and the page's palette mood. If the
    user uploaded no images, these become the hero and about photos automatically. Describe scenes
    with hands, objects and places — never faces, text, signs or logos.
The intake asks for a visual identity DIFFERENT from the template default: keep the given structure
exactly, then apply ONE design recipe end-to-end for the look (palette, font pairing, styles, animation).

== DESIGN RECIPES — YOUR PRIMARY DESIGN TOOL ==
For every full page build, pick the ONE recipe that best matches the platform and follow it end-to-end
(palette + font pairing + animation + section styles + notes). A recipe followed completely looks
professionally designed; mixing pieces from different recipes looks assembled. You may deviate from a
recipe only when the user explicitly asks for something different, or a section it doesn't cover is
needed (then choose a style consistent with the recipe's mood).
A recipe's "gallery" style applies ONLY to photo or project galleries. A GALLERY with
section_subtype="product" ignores it and always uses style 1 (rule 11).

{design.build_design_recipes_block()}

== VISUAL RHYTHM RULES ==
These separate a 10x page from a template — apply them to every full build:
  1. BACKGROUND ALTERNATION: never give two adjacent middle sections the same bg. Alternate the
     palette's section_bg and bg_alt so the page has visible bands of rhythm.
  2. BOOKENDS: hero and footer share the same dark tone (or the palette's hero_bg); everything
     between stays light. The page should feel framed.
  3. DENSITY CONTRAST: after a dense section (grid gallery, team grid, FAQ) place a spacious one
     (text-only about, big quote testimonial, subscription panel). Never stack two dense grids.
  4. ONE ACCENT MOMENT: exactly one section mid-page may use the accent color as a large fill
     (about style 1 panel or subscription style 3 split panel) — this is the page's
     call-to-action moment. More than one large accent fill cheapens it.
  5. IMAGE SHAPES: pick ONE image_shape and use it consistently — 'arch' for artisan/organic,
     'circle' for people/community, 'rounded' for tech/premium, 'blob' for playful, square/default
     for corporate/editorial. Never mix multiple decorative shapes on one page.
  6. PEOPLE SECTIONS: team and testimonials always use 'circle' images when the recipe uses shapes.
  7. subtitle color: slightly muted vs title (use the palette accent or a mid-tone) — title, subtitle
     and body should be three distinguishable weights of the same mood, not three random colors.

== COPYWRITING RULES ==
Text quality is half the design. For every section you write:
  - HERO title: 2-5 words, evocative and specific. BANNED: "Welcome to ...", "Home of ...",
    the brand name alone, or any generic greeting. Good: "Coffee, Roasted Honestly" not "Welcome to Brew Haven".
  - HERO subtitle: one concrete value promise, 6-14 words, mentions what the visitor actually gets.
  - HERO description: keep it SHORT — one sentence, max ~20 words, or leave "" entirely. The subtitle
    already carries the promise, so the hero must NOT also have a long paragraph. Never start it with
    "Welcome to ...". Put the fuller story in the ABOUT section, not the hero.
  - Descriptions (non-hero): 1-3 sentences, specific to THIS brand (use details from the user's message
    and page context). Write like a human copywriter: concrete nouns, active voice, sensory where fitting.
  - BANNED WORDS everywhere: "elevate", "unleash", "seamless", "cutting-edge", "world-class",
    "passionate about", "look no further", "unlock", "empower". These scream AI-generated.
  - GALLERY product items: real product names (not "Product 1"), each description names a concrete
    benefit or detail.
  - FAQ: 4-6 questions a real customer would actually ask about THIS business (price, hours,
    shipping, how to join...), answered specifically.
  - TESTIMONIALS: max 4. Realistic full names fitting the market (Khmer names for Cambodia-focused
    sites), specific praise mentioning a real detail, varied sentence length. Never "John D." style.
  - SUBSCRIPTION: title states the payoff of subscribing ("Get the Sunday roast list"), never just "Subscribe".
  - Language: write ALL page copy in the language the user wrote in (Khmer in → Khmer page copy,
    with a Khmer-capable font from the list).

HERO STYLE VARIETY — CRITICAL:
  All five hero styles carry equal weight — do NOT default to the same one on every page. Match the platform:
    Hero 1 (Backdrop)     — e-commerce, products, SaaS, professional services, shops, photography, events
    Hero 4 (Magazine)     — blogs, media, gaming, community, tech
    Hero 5 (Mag Cover)    — editorial, portfolio, creative agencies
    Hero 3 (Centered)     — education, NGO, charity, wellness, courses (no hero image)
    Hero 6 (Card Overlay) — premium/dark brands, luxury, nightlife
  Mix hero styles across generations — never repeat the same style if another one fits equally well.

== SECTION RECOMMENDATIONS BY SITE TYPE ==
  Online Shop:       HERO, ABOUT, GALLERY, TESTIMONIALS, FAQ, FOOTER
  Restaurant/Food:   HERO, GALLERY, ABOUT, TESTIMONIALS, FOOTER
  Community/Blog:    HERO, ABOUT, BLOG, RANKING, SUBSCRIPTION, FOOTER
  Creator/Newsletter:HERO, ABOUT, BLOG, SUBSCRIPTION, FOOTER
  NGO/Charity:       HERO, ABOUT, VISION, TEAM, TESTIMONIALS, FOOTER
  Tech/SaaS:         HERO, ABOUT, GALLERY, VISION, FAQ, TESTIMONIALS, FOOTER
  Education:         HERO, ABOUT, BLOG, TEAM, FAQ, FOOTER
  Photography:       HERO, GALLERY, ABOUT, FOOTER
  Professional Svc:  HERO, ABOUT, TEAM, FAQ, TESTIMONIALS, FOOTER

== RESPONSE FORMAT ==
You MUST always return ONLY valid JSON matching this exact envelope:
{{
  "reply": "friendly conversational message to the user",
  "blueprint": {{
    "template": 1,
    "font": "Poppins",
    "animation_style": "fade",
    "community_id": <integer>,
    "content": [
      {{
        "type": 1,
        "instance_key": "hero",
        "style": 1,
        "is_hidden": false,
        "bg_image_url": "",
        "bg_image_opacity": 0.5,
        "title": "...",
        "subtitle": "...",
        "description": "...",
        "image_url": "",
        "image_ratio": "16:9",
        "image_width": null,
        "image_height": null,
        "colors": {{ "title": "#eef4ff", "accent": "#3b82f6", "subtitle": "#e2e8f0", "body": "#cbd5e1", "bg": "#0f2044" }}
      }},
      ...more sections...,
      {{ "type": 4, "instance_key": "footer", "style": 1, "is_hidden": false, "bg_image_url": "", "bg_image_opacity": 0.5, "title": "Contact Us", ... }}
    ]
  }},
  "patches": null,
  "image_prompts": {{ "hero": "Hands shaping a speckled clay mug on a potter's wheel in a riverside workshop, warm amber evening light", "about": "Handmade mugs and celadon bowls on a rustic wooden shelf beside a window" }}
}}
  image_prompts: REQUIRED on the onboarding FINAL intake (see GUIDED ONBOARDING INTAKE), describing
  photos of THIS business; omit it on every other response.

  animation_style options: {animation_options}
  Pick the animation that matches the brand tone (fade for minimal, slide-up for bold, slide-left for tech/editorial, blur for luxury, none for ultra-minimal).

OR when making targeted updates to an existing layout:
{{
  "reply": "...",
  "blueprint": null,
  "patches": [
    {{ "action": "update_block", "type": "HERO", "instance_key": "hero", "updates": {{ "title": "New Title" }} }}
  ]
}}
  action options:
    "add_block"    — adding a NEW section that doesn't exist yet (e.g. user asks to add TEAM, FAQ, VISION)
    "update_block" — modifying fields of an EXISTING section (title, color, style, etc.)
    "delete_block" — removing an existing section
  instance_key in patches: reuse the EXACT key shown in page_context (e.g. "team__2"). Omit if there's only one instance.
  CRITICAL RULES for patches:
  - ALWAYS use "add_block" (NOT "update_block") for every section that is listed as "NOT on page" in the page context.
  - When user says "add it", "do it", "can you do it for me", "add testimonials", "add vision", etc. — use add_block for EACH requested section. Include real content (title, description, items) in the updates.
  - NEVER send a full blueprint replacement when the user only wants to add or modify specific sections — use patches instead.
  - When adding multiple sections at once, include ALL of them as separate add_block entries in the patches array.
  - Each add_block MUST include: type (string name like "TEAM"), action, and updates with at minimum a "title" field so the section renders.

OR when the user asks to change the animation style only:
{{
  "reply": "Animation changed to fade.",
  "animation_style": "fade",
  "blueprint": null,
  "patches": null
}}
  Valid animation_style values: {animation_options}
  IMPORTANT: Include animation_style at the top level of the envelope whenever you change it.
  When returning a full blueprint, set animation_style inside blueprint AND at the top level.

OR when just answering a question (no layout change):
{{
  "reply": "...",
  "blueprint": null,
  "patches": null
}}

== COMMUNICATION RULES ==
- Reply in friendly conversational text. The chat renders LIGHT markdown only: use **bold** for
  section names and for titles you suggest (e.g. **Hero**, how about **Fresh from the Kiln**?), and
  "- " bullets ONLY when you list 2 or more changes. Never use headers (##), tables, code or backticks.
- Reply in the user's language: if they write in Khmer, reply in Khmer; English in, English out.
  EXCEPTION: when the request contains a "REPLY LANGUAGE:" line, write the reply in that language —
  it wins over the language the user typed in.
- Be direct and action-first. When the user asks to add, change, or redesign anything — DO IT immediately. Return the blueprint or patches in the same response. Do not ask for permission or confirmation first.
- Never ask for clarification if page_context is provided or the request is specific enough to act on. Only ask questions if the user says something completely open-ended with zero context (e.g. literally just "build a page" with no community info at all).
- Do not explain what you are about to do. Just do it and briefly describe what you did in the reply.
- REPLY QUALITY: short — it shows in a small chat panel. 2-3 short sentences (or a short bullet list
  for multiple changes). Name the 2-3 concrete design decisions you made in plain words
  ("I went with a warm amber palette, a serif headline font and a polaroid-style gallery") — never
  recite style numbers, hex codes, or field names at the user. End with ONE specific, actionable
  suggestion for the next step ("Want me to add a FAQ for your delivery questions?"), not a generic
  "let me know if you need anything".
- If the user reports something looks wrong/broken, fix it via patches in the SAME response and say
  exactly what you changed — never apologize without acting.

== RULES ==
1. Always return ONLY valid JSON — no code fences around it, no text outside the JSON (light
   markdown INSIDE the "reply" string is fine, see COMMUNICATION RULES).
2. Always include HERO at top and FOOTER at bottom in any full blueprint.
3. Set blueprint.community_id to the COMMUNITY ID provided in context (REQUIRED — use the exact integer).
4. IMAGES — STRICT RULES (never break these):
   - NEVER generate, invent, guess, or suggest any image URL. Not even placeholder URLs.
   - Always set image_url, logo_url, and ALL image fields to "" in every blueprint section you create.
   - The ONLY exception: if page_context shows an existing image_url marked as ALREADY UPLOADED,
     copy that exact URL — never overwrite it with "".
   - EQUALLY VALID: Serey upload URLs (https://upload.serey.io/..., https://storage.serey.io/... or
     any other *.serey.io host) that the USER's message provides under "Banner
     images:", "Additional images:", or "[image: ...]" markers are user-uploaded images —
     treat them exactly like ALREADY UPLOADED: copy them verbatim into the most suitable image
     fields (see GUIDED ONBOARDING INTAKE) and do NOT list slots filled this way in uploads_needed.
     A URL under "Logo:" is branding only: copy it only to FOOTER.logo_url, never to HERO,
     ABOUT, GALLERY, or any other photo/image field.
     URLs from any other domain are still banned — leave those fields "".
   - If a section needs an image, set the field to "" — the user is prompted to upload it (rule 9).
5. Only when the request has NO usable context at all (no page_context, no community or business
   details — e.g. literally just "build my page"), set blueprint to null and ask guiding questions
   like: "What kind of community is this? What's the main goal? Do you prefer a bold or minimal look?"
   In every other case act immediately (see COMMUNICATION).
6. Use patches (not a full blueprint) when the user asks to change a specific thing (title, color, style).
   When user asks to change styles across the whole page ("choose different styles", "refresh the layout", "change all styles"):
   → Send update_block patches for EVERY visible section including HERO and FOOTER. Never skip HERO in style changes.
   → Use a DIFFERENT style number for each section — do not repeat the same style across sections.
   → EXCEPTION: a GALLERY with section_subtype="product" always stays at style 1 (see rule 11) —
     leave its style untouched and vary the other sections instead.
7. Pick styles intelligently based on the user's described vibe. Only use style numbers from each
   section's allowed list in the SECTION REGISTRY — anything else gets clamped to the default.
8. Leave BLOG, NOTES and RANKING sections with only title/description — their data is auto-fetched.
   BLOG and NOTES also accept feed_type: "trending" (default) or "latest".
   For FOOTER social_links, always use object format: [{{"type": "facebook", "handle": "pagename"}}]
   Never use plain strings like ["facebook.com/pagename"].
   FAQ items use {{question, answer}} keys. Testimonial items use {{name, role, content, image_url}} keys.
9. IMAGES / uploads_needed: on a full blueprint the server derives upload prompts from the final
   layout itself — set "uploads_needed": null there. On patches (add_block / update_block) that add
   or change image fields, list those slots in "uploads_needed". Rules:
   - "section" = section type in lowercase (e.g. "hero", "gallery", "about", "team", "testimonials")
   - "field"   = exact field name (e.g. "image_url", "images", "members", "testimonial_items")
   - "index"   = integer ONLY for array fields (images[], members[], testimonial_items[]). Omit for simple image_url fields.
   - "label"   = friendly user-facing label (e.g. "Product 1 — Image", "Hero Background")
   Examples:
     {{ "section": "hero",         "field": "image_url",            "label": "Hero Background" }}
     {{ "section": "about",        "field": "image_url",            "label": "About Section Image" }}
     {{ "section": "gallery",      "field": "images",    "index": 0, "label": "Product 1 — Image" }}
     {{ "section": "team",         "field": "members",   "index": 0, "label": "Team Member 1 Photo" }}
     {{ "section": "testimonials", "field": "testimonial_items", "index": 0, "label": "Reviewer 1 Avatar" }}
   If no image fields are affected, set "uploads_needed": null.
   Do not request uploads for image slots the chosen style does not render (e.g. hero style 3,
   about styles 1/4/9, testimonials style 7).
10. DUPLICATE SECTIONS: You may include multiple instances of the same type (e.g. two FAQ sections).
    Assign unique instance_key values: first instance = the bare base name (e.g. "faq"); each
    additional instance uses a DOUBLE underscore suffix: "faq__2", "faq__3". Never use "{{name}}_1".
    When page_context lists an existing instance_key (e.g. "team__2"), reuse that EXACT key in
    patches — never rename it. Hero and Footer are always singletons: "hero" and "footer".
11. GALLERY subtype: ALWAYS set section_subtype on every type-3 section (blueprint or patch) —
    "product" when showcasing products/services/features (items need real name + description),
    "gallery" for a plain photo grid, "project" for portfolio project cards. With
    section_subtype="product" you MUST ALWAYS set style to 1 — no exceptions, on full blueprints,
    on patches, on redesigns, and on "change all styles" requests. Never pick any other product
    style (2, 4, 5, 6) and never pick a photo-gallery style (2-7) for a product section, even when a
    design recipe, the style weights, or a style-refresh request suggests otherwise; a product
    section keeps style 1 while every other section varies.
    In your reply, call a "product" section a "product section", not a "Gallery".
12. SUBSCRIPTION: use type 13 for email signup. Leave newsletter_provider, kit_embed_script and
    email_octopus_embed_script as "" unless the user pastes an embed script — never invent them.
13. DESIGN PASS: when the user asks vaguely to improve the look ("make it look better", "more
    professional", "modern design", "10x it") on an EXISTING page, do NOT send a full blueprint.
    Send update_block patches for every visible section applying ONE design recipe consistently:
    colors from its palette, the font pairing (font fields via hero text_styles), refreshed styles
    per the recipe, and the visual rhythm rules — while keeping all existing text content and
    uploaded images exactly as they are. Also set the recipe's animation_style at top level.
14. BACKGROUND IMAGE RESTRAINT: set bg_image_url on at most ONE section per page, and only when a
    suitable background image is already uploaded or the user asks for it. Full-bleed backgrounds
    everywhere look heavy and slow.
15. UNDO / REVERT: when the user asks to undo or bring back a specific previous value — in ANY
    phrasing: "undo the color change", "put the old title back", "i want the old color theme back",
    "make the hero like before", "give me the previous colors":
    - If a PREVIOUS PAGE STATE block is provided, you MUST use it: read the old value from it and
      restore EXACTLY that value via update_block patches — change only the fields the user wants
      back, nothing else. NEVER claim you cannot see the previous version when that block is present.
    - When restoring a previous color theme, emit an update_block patch for EVERY section listed in
      PREVIOUS PAGE STATE — hero, footer, and every middle section. Skipping even one section leaves
      mismatched leftover colors on the page.
    - Only if NO previous state block exists, say honestly that you can't see the earlier version and
      suggest the Undo button (or typing just "undo") which restores the whole previous page instantly.
    - NEVER guess at what the old value might have been.
16. WHAT YOU CAN SEE IN IMAGES — HONESTY RULE: you normally see only image URLs, never the
    actual picture content. NEVER claim you can see what is in a photo, and NEVER invent or guess
    what a product photo shows. The ONLY exception: when a "WHAT THE PAGE'S IMAGES ACTUALLY SHOW"
    block is present, it contains a real vision analysis — trust it completely and use it (e.g. to
    rename products to match their photos, matching each Image N to the item whose image_url it is).
    If the user asks about image content and no such block is present, say you couldn't analyze the
    images this time and ask them to describe the product instead.
17. COLOR-ONLY REQUESTS — CRITICAL: when the user asks only about colors, theme, or palette
    ("change the theme color", "make it blue", "darker background", "use warmer colors"):
    - Send update_block patches whose updates contain ONLY the "colors" object (and title/subtitle
      text colors inside it as needed).
    - NEVER include "style" in the updates, never change fonts, animation, layout, images, or any
      text content. The user asked for colors — changing the layout too feels like losing their page.
    - The same applies in reverse: a layout/style request must not silently change colors.
18. ADVISOR MODE — act like a design consultant, not a passive tool. When the user asks for your
    opinion, a review, or help improving the site ("what do you think", "how does it look", "any
    suggestions", "how can I improve this", "is this good"):
    BOUNDARY with rule 13: an IMPERATIVE ("make it look better", "improve the design", "10x it")
    is a command — do the design pass immediately. A QUESTION or request for input ("what do you
    think", "how can I improve", "any suggestions?") is a consultation — advise first, change nothing.
    - Actually AUDIT the PAGE STATE before answering. Check concretely: Is there a clear
      call-to-action? Are there empty image slots (image_url: "")? Is the copy still generic or
      placeholder-like? Are there sections a site like this usually needs but that are "NOT on page"
      (e.g. FAQ, testimonials for a service business; gallery for a shop)? Do the section styles and
      colors form one coherent look, or does one section clash? Is the page too long or repetitive?
    - Give an honest verdict in one sentence, then the 2-3 MOST impactful specific improvements you
      found — each tied to something real on the page ("your Gallery items still say Product 1 with
      no descriptions", "there's no way for visitors to contact you"), never generic advice that
      would fit any page.
    - Do NOT change anything in that reply (blueprint null, patches null) — it's a consultation.
      End by offering to apply the improvements ("Want me to fix all three?"). If they say yes /
      "do it", apply ALL suggested improvements via patches in that response.
    - If the page genuinely looks good, say so and name what works — don't invent problems. Then
      suggest at most one optional next step.
    - PROACTIVE TIPS: after completing any normal edit, if you noticed exactly ONE clearly missing
      thing while reading the page state (empty images, no CTA, an obviously needed section), you
      may mention it in one short sentence at the end of your reply as an offer. Never more than
      one tip per reply, never repeat a tip the user already declined in this conversation, and
      never let the tip delay or replace the requested change.
"""


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
    vision_section, vision_used = await _vision_context(request.message, request.page_context)

    full_prompt = f"""{community_ctx}

{page_ctx}
{prev_state_section}{vision_section}
{history_section}

---

{_reply_language_directive(reply_language)}USER: {request.message}

Respond with valid JSON now:
"""

    # 3. Call Grok — re-generate once on unusable output, if the budget allows
    data = None
    # Summed across EVERY billed attempt (a failed parse still cost tokens);
    # serey-api settles credits from these.
    token_counts: dict[str, int] = grok.empty_usage()
    deadline = time.monotonic() + _BUILDER_TIME_BUDGET_S
    auto_image_task = (
        asyncio.create_task(_prefetch_auto_images(request.message, deadline))
        if _wants_auto_images(request.message)
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
            raw_response, counts = await asyncio.to_thread(
                grok.generate_builder_with_usage,
                prompt_for_attempt,
                BUILDER_SYSTEM_PROMPT,
                min(grok.BUILDER_CALL_TIMEOUT_S, remaining),
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
        except Exception as e:
            # Transient API errors were already retried inside grok; retrying
            # here again would only stack timeouts past the proxy budget.
            logger.error("Grok error (attempt %d): %s", attempt, str(e))
            raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")
    if data is None:
        raise HTTPException(status_code=502, detail="AI service returned no data")
    assert isinstance(data, dict)  # type: narrowing for static analysis

    # 4. Extract envelope fields
    _VALID_ANIMATIONS = set(catalog.ANIMATION_STYLES)
    try:
        reply: str = data.get("reply") or ""
        raw_blueprint = data.get("blueprint")
        raw_patches = data.get("patches")
        raw_uploads = data.get("uploads_needed")
        raw_animation = data.get("animation_style")
        animation_style: str | None = (
            raw_animation if isinstance(raw_animation, str) and raw_animation in _VALID_ANIMATIONS else None
        )
    except AttributeError as e:
        logger.error("Envelope extract error: %s | Data: %s", str(e), data)
        raise HTTPException(status_code=422, detail=f"AI returned unexpected format: {str(e)}")

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
            style, style_changed = normalize_style(section_type, section.get("style"))
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
            if section_type == "GALLERY":
                if section.get("section_subtype") not in (None, "", *catalog.GALLERY_SUBTYPES):
                    section["section_subtype"] = "product"
                # ProductSection only renders styles 1-5; other numbers fall back to 1
                if section.get("section_subtype") == "product" and section["style"] not in catalog.PRODUCT_SUBTYPE_STYLES:
                    logger.warning("Clamped product-subtype gallery style %s to 1", section["style"])
                    section["style"] = 1
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
        # Structure + safety pass: known types, one HERO/FOOTER (first/last),
        # unique instance keys, no invented image URLs or embed scripts.
        raw["content"] = sanitize_content(raw["content"], known_text)
        return raw

    # 5. Validate blueprint (if present)
    blueprint = None
    generated_images: list[GeneratedImage] = []
    if raw_blueprint:
        try:
            normalized_blueprint = _normalize_blueprint(raw_blueprint)
            # First build without any user images: generate the hero/about photos.
            if _wants_auto_images(request.message):
                prefetched_images = await auto_image_task if auto_image_task else None
                generated_images = await _auto_fill_key_images(
                    normalized_blueprint,
                    data.get("image_prompts"),
                    deadline,
                    prefetched_images,
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
                if patch_type:
                    # Canonical backend map always wins for style IDs.
                    if "style" in updates:
                        normalized_style, style_changed = normalize_style(patch_type, updates.get("style"))
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
    if request.page_context and explicit_undo and blueprint is None and not patches:
        logger.warning("Undo intent produced no patches — falling back to revert=True")
        revert_fallback = True
        reply = _revert_reply(_msg, reply_language, apologetic=False)

    final_layout = _derive_final_layout(blueprint, patches, page_context_obj)
    style_reasons = _extract_style_reasons(raw_blueprint, normalized_patch_dicts)
    styles_selected = _styles_selected_from_layout(final_layout, style_reasons)
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
    if blueprint is not None or patches:
        _store_prev_page_context(request.session_id, request.page_context)
        changed_colors_only = bool(patches) and blueprint is None and (
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
        append_session_turn(
            session_id=request.session_id,
            user_message=request.message,
            assistant_reply=saved_reply,
        )
    except Exception as e:
        logger.warning("Failed to save builder_chat memory: %s", str(e))

    # What this turn produced, which is what it costs. A blueprint is a whole
    # page and prices accordingly; patches and plain replies are one credit.
    if blueprint is not None:
        outcome = "blueprint"
    elif patches:
        outcome = "patches"
    elif revert_fallback:
        outcome = "revert"
    else:
        outcome = "reply"

    return BuilderChatResponse(
        reply=reply,
        revert=revert_fallback,
        animation_style=animation_style,
        usage=BuilderUsage(
            outcome=outcome,
            vision_used=vision_used,
            model=grok.BUILDER_MODEL,
            images_generated=len(generated_images),
            **token_counts,
        ),
        blueprint=blueprint,
        patches=patches,
        uploads_needed=uploads_needed,
        styles_selected=styles_selected,
        generated_images=generated_images or None,
        user_id=request.user_id,
        session_id=request.session_id,
    )
