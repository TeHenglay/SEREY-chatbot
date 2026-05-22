# POST /api/builder/chat — Conversational AI page builder for Serey V2 landing pages.
# The user describes or iterates on a page in plain language.
# The AI responds with a text reply AND an updated PageBlueprint (or null if not applicable).
# The blueprint matches the V2 API contract: { community_id, content: [...sections] }

import asyncio
from copy import deepcopy
from fastapi import APIRouter, HTTPException, Header, Depends
from schemas.chat import ChatRequest, BuilderChatResponse, UploadNeeded
from schemas.blueprint import PageBlueprint, PatchCommand
from services import grok
from services.layout_policy import (
    collect_rendered_upload_slots,
    compare_with_backend_map,
    derive_uploads_needed,
    normalize_section_type,
    normalize_style,
    parse_frontend_style_map,
)
from services.memory import append_session_turn, get_session_history_prompt
import json
import logging
import os
from typing import Any

router = APIRouter()
logger = logging.getLogger(__name__)

_CHAT_API_KEY = os.getenv("CHAT_API_KEY", "")


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


def _extract_style_reasons(raw_blueprint: Any, raw_patches: Any) -> dict[str, str]:
    reasons: dict[str, str] = {}
    if isinstance(raw_blueprint, dict):
        for section in raw_blueprint.get("content", []) or []:
            if not isinstance(section, dict):
                continue
            reason = section.get("style_reason")
            section_type = normalize_section_type(section.get("type"))
            if section_type and isinstance(reason, str) and reason.strip():
                reasons[section_type] = reason.strip()
    if isinstance(raw_patches, list):
        for patch in raw_patches:
            if not isinstance(patch, dict):
                continue
            top_reason = patch.get("style_reason")
            section_type = normalize_section_type(patch.get("type"))
            if section_type and isinstance(top_reason, str) and top_reason.strip():
                reasons[section_type] = top_reason.strip()
            updates = patch.get("updates")
            if not isinstance(updates, dict):
                continue
            reason = updates.get("style_reason")
            if section_type and isinstance(reason, str) and reason.strip():
                reasons[section_type] = reason.strip()
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
        if action == "delete_block":
            layout = [s for s in layout if normalize_section_type(s.get("type")) != patch_type]
            continue
        if action == "add_block":
            new_section = {"type": patch_type, **deepcopy(patch.updates)}
            layout.append(new_section)
            _normalize_section_styles(layout[-1:])
            continue
        if action == "update_block":
            target = next((s for s in layout if normalize_section_type(s.get("type")) == patch_type), None)
            if target is None:
                target = {"type": patch_type}
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
        entry = {
            "section": section_type.lower(),
            "style": int(section.get("style", 1)),
            "is_hidden": bool(section.get("is_hidden", False)),
        }
        reason = style_reasons.get(section_type)
        if reason:
            entry["style_reason"] = reason
        styles_selected.append(entry)
    return styles_selected


# ---------------------------------------------------------------------------
# System prompt — teaches the AI the complete V2 section registry and schema
# ---------------------------------------------------------------------------

BUILDER_SYSTEM_PROMPT = """You are an expert AI page builder for Serey community landing pages (V2).
Your job is to help users design their landing page through natural conversation.

== SECTION REGISTRY ==
Each page is a JSON array of section objects. Available section types:

CORE (always present unless hidden):
  HERO        — Top banner: title, subtitle, description, image_url. Styles 0-6.
  ABOUT       — About us: title, description, image_url. Styles 1-8.
  GALLERY     — Products/Services/Features: title, description, images[{image_url, name, description}].
                IMPORTANT: every image item MUST have image_url (""), name (label), and description (text). Styles 1-16.
  FOOTER      — Contact/links: title, description, phone, email, location, logo_url, social_links[]. Styles 1-3.
                IMPORTANT: If the user's message contains a phone number, put it in the "phone" field.
                If it contains an email address, put it in the "email" field.
                If it contains Facebook/Instagram/Telegram/social links, add them to "social_links" as [{"type":"facebook","handle":"pagename"}].
                Never leave phone/email blank if the user provided them.

OPTIONAL (add on demand):
  VIDEO       — Embedded videos: title, description, videos[{url,title,thumbnail}]. Styles 1-5.
  VISION      — Goals/Vision/Mission: title, description, goals_title, goals_description,
                vision_title, vision_description, mission_title, mission_description. Styles 1-6.
  BLOG        — Auto-fetches community posts: title, description only. Styles 1-6.
  TEAM        — Team members: title, description, members[{name,role,image_url}]. Styles 1,2,4,5,6,7.
  FAQ         — Q&A list: title, faq_items[{q,a}]. Styles 1-6.
  TESTIMONIALS— Customer quotes: title, testimonial_items[{name,role,quote,image_url}] (max 6). Styles 1-7.
                NOTE: style 7 = Cards No Image — omit image_url from items.
  CUSTOM      — Flexible promo: title, description, button_label, button_url, image_url, image_url_2. Styles 1-6.
  RANKING     — Auto-fetches top authors: title, description only. Styles 1-4.

== SECTION OBJECT SHAPE ==
Every section must include:
  type        — string, e.g. "HERO" (REQUIRED)
  style       — integer, e.g. 1 (REQUIRED)
  is_hidden   — boolean, default false (REQUIRED)
  colors      — object with keys: title, accent, body, bg  (plus subtitle for HERO; goal_color, vision_color, mission_color for VISION)

== COLOR DEFAULTS ==
  Light section defaults: title="#0f172a"  accent="#2b45a8"  body="#334155"  bg="#ffffff"
  Dark section defaults:  title="#eef4ff"  accent="#60a5fa"  body="#cbd5e1"  bg="#0f172a"

CRITICAL — TEXT CONTRAST RULE:
  - If a section bg is DARK (hex luminance < 0.3, e.g. #0f2044, #052e16, #1c1917, #1e1b4b):
    → ALWAYS set title="#eef4ff" or "#f0f9ff", body="#cbd5e1", subtitle="#e2e8f0"
    → NEVER use dark colors like #0f3460, #0f172a, #333, #000 for text on dark backgrounds
  - If a section bg is LIGHT (hex luminance >= 0.3, e.g. #ffffff, #f8fafc, #f0fdf4):
    → ALWAYS set title="#0f172a", body="#334155"
    → NEVER use light colors like #f0f4ff, #eef4ff for text on light backgrounds
  - Apply the correct palette-matching text colors — do not use default fallbacks when you have picked a palette

== STYLE DESCRIPTIONS ==

HERO styles:
  1 = Two-column: text left, image right. Clean and professional.
  2 = Full-bleed cinematic image with dark gradient overlay. All text centered, white. Bold/dramatic.
  3 = Full-bleed image + centered text, lighter overlay. Energetic/playful.
  4 = Full-bleed image + text pinned to the LEFT with light overlay. Organized/editorial.
  5 = Magazine split: image fills LEFT half, text on RIGHT. Sophisticated/editorial.
  6 = Minimal dark (bg #0f172a). Huge centered title, image below text. Premium/dark.
  0 = Full-width bg image with overlay, centered content. Classic/neutral.

ABOUT styles:
  1 = Image left (rectangular), text right. Clean.
  2 = Circular image LEFT, underline + title RIGHT. Modern.
  3 = Text LEFT with color underline, circular image RIGHT. Friendly.
  4 = Text LEFT with underline, rectangular image RIGHT. Editorial.
  5 = Text only, left-aligned, accent underline. No image. Minimal.
  6 = Text only, centered, accent underline. No image. Clean/centered.
  7 = Split panel: colored left half (accent bg) + image, white right with text. Bold/brand.
  8 = Colored strip left (accent bg, no image), white right with text. Dark/dramatic.

GALLERY styles:
  2  = Product cards — image top, name + description below. Best for products.
  3  = List view — image left, name + description right. Good for services.
  4  = Featured grid — 1 large image left, 2×2 small grid right. Bold showcase.
  6  = CSS masonry — natural varying heights. Best for photography.
  9  = Polaroid — white-bordered cards with caption. Playful/creative.
  10 = Cinematic 16:9 widescreen stacked with hover overlay. Dark/dramatic.
  13 = Magazine — 1 large main LEFT, 2 stacked RIGHT. Editorial.
  15 = Zigzag — alternating image left/right with text. Product showcase.
  16 = Wall — tight no-gap grid. Photography/portfolio.
  (other gallery styles 1,5,7,8,11,12,14 are additional layout variants)

CUSTOM styles:
  1 = Split Right: text left, image right. Professional.
  2 = Split Left: image left, text right. Professional.
  3 = Centered: image above, centered title and text. Minimal.
  4 = Banner: full-width image background, dark overlay, white centered text. Bold.
  5 = Card: image on top of styled card with accent underline. Playful.
  6 = Highlight split: accent-colored LEFT panel (title+desc+button), white RIGHT with 1-2 images. Brand.

VIDEO styles:
  1 = Classic grid — thumbnails in a clean grid layout.
  2 = Dark — dark background, video cards with glow effects.
  3 = Split — large featured video left, playlist right.
  4 = Cards — video thumbnails as styled cards.
  5 = Showcase — hero-style large single video with description.

VISION styles:
  1 = 3 cards with accent icon circles, split layout.
  2 = 3-column colored cards. Each card bg = its color (goal/vision/mission).
  3 = Horizontal icon rows with number on right.
  4 = Numbered steps — dark style.
  5 = Feature grid — icon circle, title, description, centered.
  6 = Split panel — accent-bg column left, list of icon rows right.

BLOG styles:
  1 = Grid — card grid with image, title, excerpt.
  2 = List — vertical list with image left, text right.
  3 = Magazine — editorial large+small layout.
  4 = Minimal — text-only clean list.
  5 = Overlay — image cards with text overlay on hover.
  6 = Editorial — magazine-style with featured post.

TEAM styles:
  1 = Grid — cards with photo, name, role.
  2 = Cards — elevated cards with accent border.
  4 = List — horizontal rows with photo left, bio right.
  5 = Banner — full-width strip per member.
  6 = Spotlight — large featured layout.
  7 = Staggered — alternating left/right layout.

FAQ styles:
  1 = Accordion — expandable questions, minimal.
  2 = Two Column — questions split into two columns.
  3 = Split — category sidebar left, answers right.
  4 = Left Border — questions with colored left border accent.
  5 = Cards — each Q&A in a card.
  6 = Numbered — numbered list style.

TESTIMONIALS styles:
  1 = Cards — photo + quote cards in a grid.
  2 = Large Quote — single large centered quote.
  3 = Side by Side — two-column quote layout.
  4 = Minimal List — clean stacked list.
  5 = Left Border — quotes with accent left border.
  6 = Dark — dark background with glowing cards.
  7 = Cards No Image — cards without author photos (omit image_url from items).

RANKING styles:
  1 = List — ranked list with rank number, name, score.
  2 = Podium — top 3 on a podium, others below.
  3 = Cards — each author as a card.
  4 = Circles — circular avatar layout.

FOOTER styles:
  1 = Dark navy — logo + contact left, social icons + copyright bottom strip.
  2 = Light minimal centered — logo, title, contact, social, copyright.
  3 = Dark 3-column grid — logo/tagline, contact, follow-us columns.

== STYLE GUIDE (by personality) ==
  Clean/Minimal:      Hero 1, About 6, Gallery 2,  Custom 3, Footer 2
  Cinematic/Bold:     Hero 2, About 7, Gallery 4,  Custom 4, Footer 1
  Magazine/Editorial: Hero 5, About 4, Gallery 13, Custom 6, Footer 3
  Dark/Dramatic:      Hero 6, About 8, Gallery 10, Custom 4, Footer 1
  Playful/Creative:   Hero 3, About 2, Gallery 9,  Custom 5, Footer 2
  Organized/Corporate:Hero 4, About 3, Gallery 3,  Custom 2, Footer 3
  Photography:        Hero 5, About 5, Gallery 6,  Custom 2, Footer 1
  Product Showcase:   Hero 1, About 4, Gallery 15, Custom 1, Footer 2

HERO STYLE VARIETY — CRITICAL:
  Do NOT default to Hero style 2 (Cinematic) for every page. It is ONLY appropriate for:
  Photography portfolios, high-budget events, fashion/luxury brands.
  For most platforms, prefer these instead:
    Hero 1 (Split)    — e-commerce, products, SaaS, professional services, shops
    Hero 5 (Magazine) — blogs, media, gaming, community, portfolio, tech
    Hero 3 (Centered) — education, NGO, charity, wellness, courses
    Hero 4 (Banner)   — events, booking, announcements, restaurants
    Hero 6 (Minimal)  — agencies, portfolio, premium/dark brands
  Mix hero styles across generations — never repeat style 2 if another style fits equally well.

== SECTION RECOMMENDATIONS BY SITE TYPE ==
  Online Shop:       HERO, ABOUT, GALLERY, TESTIMONIALS, FAQ, FOOTER
  Restaurant/Food:   HERO, GALLERY, ABOUT, TESTIMONIALS, FOOTER
  Community/Blog:    HERO, ABOUT, BLOG, RANKING, FOOTER
  NGO/Charity:       HERO, ABOUT, VISION, TEAM, TESTIMONIALS, FOOTER
  Tech/SaaS:         HERO, ABOUT, GALLERY, VISION, FAQ, TESTIMONIALS, FOOTER
  Education:         HERO, ABOUT, BLOG, TEAM, FAQ, FOOTER
  Photography:       HERO, GALLERY, ABOUT, FOOTER
  Professional Svc:  HERO, ABOUT, TEAM, FAQ, CUSTOM, FOOTER

== RESPONSE FORMAT ==
You MUST always return ONLY valid JSON matching this exact envelope:
{
  "reply": "friendly conversational message to the user",
  "blueprint": {
    "community_id": <integer>,
    "content": [
      {
        "type": "HERO",
        "style": 1,
        "is_hidden": false,
        "title": "...",
        "subtitle": "...",
        "description": "...",
        "image_url": "",
        "colors": { "title": "#eef4ff", "accent": "#3b82f6", "subtitle": "#e2e8f0", "body": "#cbd5e1", "bg": "#0f2044" }
      },
      ...more sections...,
      { "type": "FOOTER", "style": 1, "is_hidden": false, "title": "Contact Us", ... }
    ]
  },
  "patches": null
}

OR when making targeted updates to an existing layout:
{
  "reply": "...",
  "blueprint": null,
  "patches": [
    { "action": "update_block", "type": "HERO", "updates": { "title": "New Title" } }
  ]
}
  action options:
    "add_block"    — adding a NEW section that doesn't exist yet (e.g. user asks to add TEAM, FAQ, VISION)
    "update_block" — modifying fields of an EXISTING section (title, color, style, etc.)
    "delete_block" — removing an existing section
  CRITICAL RULES for patches:
  - ALWAYS use "add_block" (NOT "update_block") for every section that is listed as "NOT on page" in the page context.
  - When user says "add it", "do it", "can you do it for me", "add testimonials", "add vision", etc. — use add_block for EACH requested section. Include real content (title, description, items) in the updates.
  - NEVER send a full blueprint replacement when the user only wants to add or modify specific sections — use patches instead.
  - When adding multiple sections at once, include ALL of them as separate add_block entries in the patches array.
  - Each add_block MUST include: type, action, and updates with at minimum a "title" field so the section renders.

OR when just answering a question (no layout change):
{
  "reply": "...",
  "blueprint": null,
  "patches": null
}

== COMMUNICATION RULES ==
- Always reply in plain, friendly conversational text. Never use markdown: no asterisks, no bullet points, no bold (**text**), no headers (##), no backticks.
- Be direct and action-first. When the user asks to add, change, or redesign anything — DO IT immediately. Return the blueprint or patches in the same response. Do not ask for permission or confirmation first.
- Never ask for clarification if page_context is provided or the request is specific enough to act on. Only ask questions if the user says something completely open-ended with zero context (e.g. literally just "build a page" with no community info at all).
- Do not explain what you are about to do. Just do it and briefly describe what you did in the reply.

== RULES ==
1. Always return ONLY valid JSON — no markdown, no backticks, no text outside the JSON.
2. Always include HERO at top and FOOTER at bottom in any full blueprint.
3. Set blueprint.community_id to the COMMUNITY ID provided in context (REQUIRED — use the exact integer).
4. IMAGES — STRICT RULES (never break these):
   - NEVER generate, invent, guess, or suggest any image URL. Not even placeholder URLs.
   - Always set image_url, logo_url, and ALL image fields to "" in every blueprint section you create.
   - The ONLY exception: if page_context shows an existing image_url marked as ALREADY UPLOADED,
     copy that exact URL — never overwrite it with "".
   - If a section needs an image, set the field to "" and include it in uploads_needed so the user
     can upload via the upload flow.
5. If the user is vague (e.g. "build my page"), set blueprint to null and ask guiding questions
   like: "What kind of community is this? What's the main goal? Do you prefer a bold or minimal look?"
6. Use patches (not a full blueprint) when the user asks to change a specific thing (title, color, style).
   When user asks to change styles across the whole page ("choose different styles", "refresh the layout", "change all styles"):
   → Send update_block patches for EVERY visible section including HERO and FOOTER. Never skip HERO in style changes.
   → Use a DIFFERENT style number for each section — do not repeat the same style across sections.
7. Pick styles intelligently based on the user's described vibe.
8. Leave BLOG and RANKING sections with only title/description — their data is auto-fetched.
   For FOOTER social_links, always use object format: [{"type": "facebook", "handle": "pagename"}]
   Never use plain strings like ["facebook.com/pagename"].
9. IMAGES: Whenever you create or update a section with image fields, always include "uploads_needed"
   in your JSON response. Rules:
   - "section" = section type in lowercase (e.g. "hero", "gallery", "about", "team", "custom", "testimonials")
   - "field"   = exact field name (e.g. "image_url", "images", "members", "testimonial_items")
   - "index"   = integer ONLY for array fields (images[], members[], testimonial_items[]). Omit for simple image_url fields.
   - "label"   = friendly user-facing label (e.g. "Product 1 — Image", "Hero Background")
   Examples:
     { "section": "hero",         "field": "image_url",            "label": "Hero Background" }
     { "section": "about",        "field": "image_url",            "label": "About Section Image" }
     { "section": "custom",       "field": "image_url",            "label": "Custom Section Image" }
     { "section": "custom",       "field": "image_url_2",          "label": "Custom Section Image 2" }
     { "section": "gallery",      "field": "images",    "index": 0, "label": "Product 1 — Image" }
     { "section": "team",         "field": "members",   "index": 0, "label": "Team Member 1 Photo" }
     { "section": "testimonials", "field": "testimonial_items", "index": 0, "label": "Reviewer 1 Avatar" }
   If no image fields are affected, set "uploads_needed": null.
   On a full redesign (blueprint), ALWAYS include uploads_needed for every section that has image
   fields — even if page_context had images before. New layout = new upload prompts.
"""


@router.post("/builder/chat", response_model=BuilderChatResponse, dependencies=[Depends(_verify_api_key)])
async def builder_chat(request: ChatRequest):
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

    full_prompt = f"""{community_ctx}

{page_ctx}

{history_section}

---

USER: {request.message}

Respond with valid JSON now:
"""

    # 3. Call Grok — retry once on malformed JSON
    data = None
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
        try:
            raw_response = await asyncio.to_thread(grok.generate_builder, full_prompt, BUILDER_SYSTEM_PROMPT)
            cleaned = _clean_raw(raw_response)
            if not cleaned:
                raise ValueError("Model returned empty content after fence stripping")
            # If model returned plain text instead of JSON, wrap it as a reply-only envelope
            if not cleaned.startswith("{"):
                logger.warning("Model returned plain text instead of JSON — wrapping as reply: %s", cleaned[:200])
                data = {"reply": cleaned, "blueprint": None, "patches": None}
                break
            data = json.loads(cleaned)
            break
        except json.JSONDecodeError as e:
            logger.error("JSON parse error (attempt %d): %s | Raw: %s", attempt, str(e), raw_response[:600])
            if attempt == 2:
                raise HTTPException(status_code=422, detail=f"AI returned malformed JSON after retry: {str(e)}")
        except Exception as e:
            logger.error("Grok error (attempt %d): %s", attempt, str(e))
            if attempt == 2:
                raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")
    if data is None:
        raise HTTPException(status_code=502, detail="AI service returned no data")
    assert isinstance(data, dict)  # type: narrowing for static analysis

    # 4. Extract envelope fields
    try:
        reply: str = data.get("reply") or ""
        raw_blueprint = data.get("blueprint")
        raw_patches = data.get("patches")
        raw_uploads = data.get("uploads_needed")
    except AttributeError as e:
        logger.error("Envelope extract error: %s | Data: %s", str(e), data)
        raise HTTPException(status_code=422, detail=f"AI returned unexpected format: {str(e)}")

    def _normalize_blueprint(raw: dict) -> dict:
        """Fix common AI field name mismatches before Pydantic validation."""
        for section in raw.get("content", []):
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
            # Gallery images: normalize field names + ensure name/description exist
            for img in section.get("images", []) or []:
                if "url" in img and "image_url" not in img:
                    img["image_url"] = img.pop("url")
                if "title" in img and "name" not in img:
                    img["name"] = img.pop("title")
                # Never carry over a non-empty image_url from a redesign — only keep if it
                # was explicitly set to a real CDN URL (starts with http). If AI invented
                # a URL or copied a wrong one it gets cleared to "".
                url = img.get("image_url", "")
                if url and not url.startswith("http"):
                    img["image_url"] = ""
                # Ensure name and description always exist
                img.setdefault("name", "")
                img.setdefault("description", "")
            # Footer social_links: {platform} → {type}
            for link in section.get("social_links", []) or []:
                if "platform" in link and "type" not in link:
                    link["type"] = link.pop("platform")
        return raw

    # 5. Validate blueprint (if present)
    blueprint = None
    if raw_blueprint:
        try:
            blueprint = PageBlueprint(**_normalize_blueprint(raw_blueprint))
        except Exception as e:
            logger.error("Blueprint validation failed: %s | Data: %s", str(e), raw_blueprint)
            raise HTTPException(
                status_code=422,
                detail=f"AI returned invalid blueprint structure: {str(e)}",
            )

    # 6. Validate patches (if present)
    patches = None
    normalized_patch_dicts: list[dict[str, Any]] = []
    if raw_patches and isinstance(raw_patches, list):
        try:
            normalized = []
            for p in raw_patches:
                # AI sometimes uses { action, block/new_block: {type, ...} } instead of { action, type, updates }
                raw_block = p.get("block") or p.get("new_block")
                if raw_block and "type" not in p:
                    p = {
                        "action": p["action"],
                        "type": raw_block.get("type", ""),
                        "updates": {k: v for k, v in raw_block.items() if k != "type"},
                    }
                patch_type = normalize_section_type(p.get("type"))
                p["type"] = patch_type
                updates = p.get("updates")
                if not isinstance(updates, dict):
                    updates = {}
                    p["updates"] = updates
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
                normalized.append(p)
            normalized_patch_dicts = normalized
            patches = [PatchCommand(**p) for p in normalized_patch_dicts]
        except Exception as e:
            logger.error("Patches validation failed: %s | Data: %s", str(e), raw_patches)
            raise HTTPException(
                status_code=422,
                detail=f"AI returned invalid patch structure: {str(e)} | Raw patches: {raw_patches}",
            )

    final_layout = _derive_final_layout(blueprint, patches, page_context_obj)
    style_reasons = _extract_style_reasons(raw_blueprint, normalized_patch_dicts)
    styles_selected = _styles_selected_from_layout(final_layout, style_reasons)
    _validate_ai_uploads_against_layout(raw_uploads, final_layout)
    uploads_needed = None
    if final_layout is not None:
        uploads_needed = [UploadNeeded(**u) for u in derive_uploads_needed(final_layout)]

    # 7. Save this turn to session history (non-critical)
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

    return BuilderChatResponse(
        reply=reply,
        blueprint=blueprint,
        patches=patches,
        uploads_needed=uploads_needed,
        styles_selected=styles_selected,
        user_id=request.user_id,
        session_id=request.session_id,
    )
