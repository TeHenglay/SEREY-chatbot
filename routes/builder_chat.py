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
    normalize_gallery_subtype,
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
        section["type"] = section_type
        # GALLERY: resolve photo-vs-product subtype before clamping (style ranges differ).
        subtype = normalize_gallery_subtype(section)
        if subtype is not None:
            section["section_subtype"] = subtype
        style, changed = normalize_style(section_type, section.get("style"), subtype)
        if changed:
            logger.warning(
                "Adjusted invalid style for section=%s subtype=%s from=%s to=%s based on backend canonical map",
                section_type,
                subtype,
                section.get("style"),
                style,
            )
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
# System prompt — teaches the AI the complete V2 section registry and schema
# ---------------------------------------------------------------------------

BUILDER_SYSTEM_PROMPT = """You are an expert AI page builder for Serey community landing pages (V2).
Your job is to help users design their landing page through natural conversation.

== SECTION TYPE IDs ==
Use numeric type IDs in all JSON output:
  1 = HERO, 2 = ABOUT, 3 = GALLERY, 4 = FOOTER,
  5 = VIDEO, 6 = VISION, 7 = BLOG, 8 = TEAM,
  9 = FAQ, 10 = TESTIMONIALS, 11 = CUSTOM, 12 = RANKING, 13 = SUBSCRIPTION

== SECTION REGISTRY ==
Each page is a JSON array of section objects. Available section types:

CORE (always present unless hidden):
  1 (HERO)    — Top banner: title, subtitle, description, image_url, image_ratio ("16:9"), image_shape. Styles 1,2,3,5,7,8.
                NOTE: style 3 is CENTERED TEXT-ONLY — do NOT include image_url for hero style 3.
  2 (ABOUT)   — About us: title, description, image_url, image_ratio ("16:9"), image_shape. Styles 1,2,4,5,7,8,10,11.
                NOTE: styles 5 and 8 are TEXT-ONLY — do NOT include image_url for those.
  3 (GALLERY) — type 3 splits into TWO different components via "section_subtype". You MUST set it:
                • section_subtype="gallery"  → photo gallery. Items are images only: images[{image_url}].
                  name is an optional caption (Polaroid/Cinematic/Triptych). No price/description shown. Styles 1-9,11,12.
                • section_subtype="product"   → product/service/feature cards. Items have name + description shown
                  prominently: images[{image_url, name, description}]. Styles 1-5.
                DECISION: items being SOLD or DESCRIBED (name+description) → "product". Pure photos → "gallery".
                Always send "product" (never "project") for the card variant. Never mix style numbers between subtypes.
  4 (FOOTER)  — Contact/links: title, description, phone, email, location, logo_url, social_links[],
                privacy_url, terms_url. Styles 1,2,3,4,5. (privacy_url/terms_url show in styles 2 and 5.)
                IMPORTANT: If the user's message contains a phone number, put it in the "phone" field.
                If it contains an email address, put it in the "email" field.
                If it contains Facebook/Instagram/Telegram/social links, add them to "social_links" as [{"type":"facebook","handle":"pagename"}].
                Never leave phone/email blank if the user provided them.

OPTIONAL (add on demand):
  5 (VIDEO)   — Embedded videos: title, description, videos[{url,title,thumbnail}]. Styles 1,2,3,4.
  6 (VISION)  — Goals/Vision/Mission: title, description, goals_title, goals_description,
                vision_title, vision_description, mission_title, mission_description. Styles 1-7.
  7 (BLOG)    — Auto-fetches community posts: title, description, feed_type ("trending" default | "latest"). Styles 1-6.
  8 (TEAM)    — Team members: title, description, members[{name,role,image_url}]. Styles 1,2,4,5,6,7,8.
  9 (FAQ)     — Q&A list: title, faq_items[{question,answer}]. Styles 1-7.
  10 (TESTIMONIALS) — Customer quotes: title, testimonial_items[{name,role,content,image_url}] (max 6). Styles 1,3,4,5,6,7,9,10.
                NOTE: style 7 = Cards No Image — omit image_url from items.
  11 (CUSTOM) — Flexible promo: title, description, button_label, button_url, image_url, image_shape. Styles 1-7.
  12 (RANKING)— Auto-fetches top authors: title, description, authors (leave as []). Style 1 only.
  13 (SUBSCRIPTION) — Membership/subscribe call-to-action: title, description. Style 1 only.

== SECTION OBJECT SHAPE ==
Every section must include:
  type              — integer type ID, e.g. 1 for HERO (REQUIRED)
  style             — integer, e.g. 1 (REQUIRED)
  section_subtype   — REQUIRED for GALLERY (type 3) only: "gallery" or "product". Omit for all other types.
  is_hidden         — boolean, default false (REQUIRED)
  instance_key      — string, e.g. "team_1". REQUIRED for all sections. First instance = "{name}_1". Singletons: "hero", "footer".
  colors            — object with keys: title, accent, body, bg  (plus subtitle for HERO; goal_color, vision_color, mission_color for VISION)
  image_shape       — optional, HERO/ABOUT/CUSTOM image_url only: square | rounded | circle | arch | diamond | hexagon | blob | star
  bg_image_url      — always set to "" (user-uploaded, AI must never invent URLs)
  bg_image_opacity  — float 0.0–1.0, default 0.5

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

== STYLE DESCRIPTIONS (Builder V2) ==
Each style is tagged with its image need: [img required] / [img optional] / [no image].
Only suggest [img required] styles when the user has a photo. Prefer [no image] styles when they don't.

HERO styles (1,2,3,5,7,8):
  1 = Two Column — text left, image right. [img optional]
  2 = Full-Bleed Cinematic — image fills section, dark overlay, white text. [img required] photography/fashion/luxury only.
  3 = Centered — solid bg, centered text, NO image slot. [no image] ideal when user has no hero photo.
  5 = Magazine Split — image fills LEFT half, text RIGHT. [img required] best with portrait photos.
  7 = Editorial Magazine Cover — top/bottom rules, accent label + large title left, image right. [img optional]
  8 = Padded Card — image fills a rounded card, white text overlaid. [img required]

ABOUT styles (1,2,4,5,7,8,10,11):
  1 = Default Two Column — image left, title+description right. [img optional]
  2 = Circular Image Left — circular image left, accent-underlined title right. [img optional]
  4 = Text Left, Image Right — underlined title + text left, rectangular image right. [img optional]
  5 = Text Only Left-Aligned — accent underline, body text, NO image. [no image]
  7 = Panel with Image — accent-colored left half with image, text right. [img optional]
  8 = Panel Text Only — thin accent strip left, text, NO image. [no image]
  10 = Spotlight — text + tag chip left, offset image frame right. [img optional]
  11 = Editorial — image left, title + accent separator + text right. [img optional]

GALLERY — section_subtype="gallery" (photo) styles (1,2,3,4,5,6,7,8,9,11,12): [all img required]
  1 = Classic Grid (3-up). 2 = Featured R (2×2 + 1 large). 3 = Masonry (varying heights, great for photography).
  4 = Spotlight (1 full-width hero + 3 thumbs). 5 = Strip (horizontal scroll). 6 = Polaroid (white cards, captions).
  7 = Cinematic (16:9 stacked, name overlay). 8 = Triptych (3 tall columns). 9 = Overlap (staggered cards).
  11 = Wall (tight no-gap grid). 12 = Editorial Photo Essay (rule + label + asymmetric grid).

GALLERY — section_subtype="product" (cards w/ name+description) styles (1,2,3,4,5):
  1 = Cards — image top, name + description below. [img optional]
  2 = List — small image left, name + accent bar + description right. [img optional]
  3 = Feature — 1 large featured image left, 2×2 grid right. [img required]
  4 = Editorial Strip — numbered rows (01,02…), name+desc center, small image right. [img optional]
  5 = Shop Shelf — e-commerce grid, badge + "Product" tag + name + desc. [img required]

CUSTOM styles (1-7): [all img optional]
  1 = Split Right (text left, image right). 2 = Split Left (image left, text right). 3 = Centered (image top, centered).
  4 = Banner (full-width colored band, title+desc left, CTA right). 5 = Card (content in bordered card).
  6 = Highlight (accent band with padding). 7 = Editorial Feature Spread (rule + accent label + title + image/text).

VIDEO styles (1,2,3,4): [all need video URLs]
  1 = Horizontal Row (3 players in a row, ▶ badge). 2 = Split (text left, players right).
  3 = Showcase (1 large + 2 sidebar). 4 = Film Review (editorial rule + label + row + description).

VISION styles (1-7): [all no image]
  1 = Cards (icon + title + desc grid). 2 = 3-Column Colored Cards. 3 = Horizontal Icon Rows.
  4 = Numbered Steps Dark. 5 = Feature Grid (1 featured + smaller). 6 = Split Panel (heading left, items right).
  7 = Editorial Columns (rule + accent label + title + 3-column cards).

BLOG styles (1-6): [no image — posts auto-fetched] Use feed_type "trending" (default) or "latest".
  1 = Grid. 2 = List. 3 = Magazine. 4 = Minimal. 5 = Overlay. 6 = Editorial.

TEAM styles (1,2,4,5,6,7,8):
  1 = Grid (avatar falls back to initial). [photos optional]
  2 = Horizontal Cards. [photos optional]
  4 = Minimal List (small avatar + name + rule + role). [photos optional — best when no photos]
  5 = Banner Cards (tall portrait fills card). [photos important]
  6 = Spotlight (large photo left). [photos important]
  7 = Staggered Split (offset columns). [photos important]
  8 = Editorial Portrait Rows (square portrait + name + accent line + role/bio). [photos optional]

FAQ styles (1-7): [bg image only — no foreground image]
  1 = Accordion. 2 = Two Columns. 3 = Split (title/desc left, accordion right). 4 = Left Border.
  5 = Cards (white card bg — keep title/body dark even on dark section bg). 6 = Numbered. 7 = Editorial Q&A.

TESTIMONIALS styles (1,3,4,5,6,7,9,10):
  1 = Cards Grid (avatar falls back to initials). [photos optional]
  3 = Side by Side (quote + accent rule + avatar inline). [photos optional]
  4 = Minimal List (left accent bar). [photos optional]
  5 = Left Border Cards. [photos optional]
  6 = Speech Bubble. [photos optional]
  7 = Cards No Image — NO avatars; omit image_url from items. [no image]
  9 = Large Quote (single featured display quote). [photos optional]
  10 = Editorial Pull Quote (rules + large ❝ + name·role). [photos optional]

RANKING styles: 1 only — ranked list, auto-fetched authors. [no image]

SUBSCRIPTION styles: 1 only — membership/subscribe CTA (title + description). [no image]

FOOTER styles (1,2,3,4,5): [logo optional]
  1 = Dark Navy (single column). 2 = Minimal Centered Light (shows privacy/terms links).
  3 = Three Columns Dark. 4 = Gradient Split (light branding left, dark contact right).
  5 = Editorial (horizontal rules, shows privacy/terms links).

== STYLE GUIDE (by personality) ==
  Clean/Minimal:      Hero 3, About 5, Gallery(product) 1, Custom 3, Footer 2
  Cinematic/Bold:     Hero 2, About 7, Gallery(photo) 4,  Custom 4, Footer 1
  Magazine/Editorial: Hero 7, About 11, Gallery(photo) 12, Custom 7, Footer 5
  Dark/Dramatic:      Hero 8, About 8, Gallery(photo) 7,  Custom 4, Footer 3
  Playful/Creative:   Hero 1, About 2, Gallery(photo) 6,  Custom 5, Footer 2
  Organized/Corporate:Hero 5, About 4, Gallery(product) 5, Custom 2, Footer 3
  Photography:        Hero 5, About 5, Gallery(photo) 3,  Custom 2, Footer 1
  Product Showcase:   Hero 1, About 4, Gallery(product) 5, Custom 1, Footer 4

HERO STYLE VARIETY — CRITICAL:
  Do NOT default to Hero style 2 (Cinematic) for every page. It is ONLY appropriate for:
  Photography portfolios, high-budget events, fashion/luxury brands (and needs a strong photo).
  For most platforms, prefer these instead:
    Hero 1 (Two Column)  — e-commerce, products, SaaS, professional services, shops
    Hero 5 (Magazine)    — blogs, media, gaming, portfolio, tech (needs a photo)
    Hero 7 (Editorial)   — publishers, editorial, magazines (works without a photo)
    Hero 3 (Centered)    — no-photo sites, education, NGO, wellness, courses (NO image)
    Hero 8 (Padded Card) — premium/dark brands (needs a photo)
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
    "template": 1,
    "font": "Roboto",
    "animation_style": "fade",
    "community_id": <integer>,
    "content": [
      {
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
        "colors": { "title": "#eef4ff", "accent": "#3b82f6", "subtitle": "#e2e8f0", "body": "#cbd5e1", "bg": "#0f2044" }
      },
      ...more sections...,
      { "type": 4, "instance_key": "footer", "style": 1, "is_hidden": false, "bg_image_url": "", "bg_image_opacity": 0.5, "title": "Contact Us", ... }
    ]
  },
  "patches": null
}

  animation_style options: "none" | "fade" | "slide-up" | "slide-left" | "blur"
  Pick the animation that matches the brand tone (fade for minimal, slide-up for bold, blur for luxury).

OR when making targeted updates to an existing layout:
{
  "reply": "...",
  "blueprint": null,
  "patches": [
    { "action": "update_block", "type": "HERO", "instance_key": "hero", "updates": { "title": "New Title" } }
  ]
}
  action options:
    "add_block"    — adding a NEW section that doesn't exist yet (e.g. user asks to add TEAM, FAQ, VISION)
    "update_block" — modifying fields of an EXISTING section (title, color, style, etc.)
    "delete_block" — removing an existing section
  instance_key in patches: use to target a specific instance (e.g. "team_2"). Omit if there's only one.
  CRITICAL RULES for patches:
  - ALWAYS use "add_block" (NOT "update_block") for every section that is listed as "NOT on page" in the page context.
  - When user says "add it", "do it", "can you do it for me", "add testimonials", "add vision", etc. — use add_block for EACH requested section. Include real content (title, description, items) in the updates.
  - NEVER send a full blueprint replacement when the user only wants to add or modify specific sections — use patches instead.
  - When adding multiple sections at once, include ALL of them as separate add_block entries in the patches array.
  - Each add_block MUST include: type (string name like "TEAM"), action, and updates with at minimum a "title" field so the section renders.

OR when the user asks to change the animation style only:
{
  "reply": "Animation changed to fade.",
  "animation_style": "fade",
  "blueprint": null,
  "patches": null
}
  Valid animation_style values: "none" | "fade" | "slide-up" | "slide-left" | "blur"
  IMPORTANT: Include animation_style at the top level of the envelope whenever you change it.
  When returning a full blueprint, set animation_style inside blueprint AND at the top level.

OR when the user asks to change the site/global font only:
{
  "reply": "Switched the site font to Poppins.",
  "font": "Poppins",
  "blueprint": null,
  "patches": null
}
  Put the chosen font (one of the FONTS list) in "font" at the top level. Do NOT add or change any sections.
  When returning a full blueprint, set "font" inside blueprint AND at the top level.

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

== CONVERSATION CONTEXT — READ THIS FIRST EVERY TURN ==
- ALWAYS read CONVERSATION HISTORY before deciding what the user means. The newest user message is almost always a CONTINUATION of the current topic, not a fresh request.
- If YOUR last message asked the user a question, the user's next message is the ANSWER to that question. Resolve it in that context — do not reinterpret it as an unrelated command.
  Example: you asked "Which font should I switch to?" →
    • "what do you have?" / "what are my options?" → list available fonts from the FONTS section (do NOT list or add sections).
    • a font name (e.g. "Poppins", "the serif one") → apply it via the font-only envelope.
    • "all of them" / "you pick" → choose the best-fitting font and apply it.
- Stay on the current topic. While discussing fonts, colors, animation, or a specific section, a vague reply ("what do you have?", "all", "yes", "you choose") refers to THAT topic — never silently add or remove sections because of it.
- Only add/remove sections when the user clearly names sections or asks to change the page's sections. If genuinely ambiguous, ask one short clarifying question instead of guessing.

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
8. Leave BLOG, RANKING and SUBSCRIPTION sections with only title/description — their data is auto-fetched.
   BLOG may also set feed_type ("trending" or "latest").
   For FOOTER social_links, always use object format: [{"type": "facebook", "handle": "pagename"}]
   Never use plain strings like ["facebook.com/pagename"]. Add privacy_url/terms_url if the user mentions them.
   FAQ items use {question, answer} keys. Testimonial items use {name, role, content, image_url} keys.
   GALLERY (type 3): you MUST set section_subtype ("gallery" for photos, "product" for cards with name+description).
   Product items need name + description; photo items need only image_url. Never use "project" — send "product".
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
     { "section": "gallery",      "field": "images",    "index": 0, "label": "Gallery Photo 1" }     (subtype gallery)
     { "section": "gallery",      "field": "images",    "index": 0, "label": "Product 1 — Image" }   (subtype product)
     { "section": "team",         "field": "members",   "index": 0, "label": "Team Member 1 Photo" }
     { "section": "testimonials", "field": "testimonial_items", "index": 0, "label": "Reviewer 1 Avatar" }
   If no image fields are affected, set "uploads_needed": null.
   On a full redesign (blueprint), ALWAYS include uploads_needed for every section that has image
   fields — even if page_context had images before. New layout = new upload prompts.
10. DUPLICATE SECTIONS: You may include multiple instances of the same type (e.g. two FAQ sections).
    Assign unique instance_key values: first = "{name}_1" (e.g. "faq_1"), second = "{name}_2", etc.
    Hero and Footer are always singletons — use instance_key "hero" and "footer" respectively.

== FONTS ==
Set "font" (global) and optionally per-section text_styles.title_font / subtitle_font / description_font.
Pick fonts that match the brand. Available families (loaded via Google Fonts):
  Sans-serif: Inter, Roboto, Poppins, Montserrat, Nunito Sans, Barlow Condensed, Figtree,
    Plus Jakarta Sans, Outfit, Manrope, Syne, Lexend, Cabin, Mulish, Karla, Jost, Urbanist, Space Grotesk
  Serif: Playfair Display, Lora, PT Serif, Libre Baskerville, Crimson Text, EB Garamond, Spectral, Bitter, Bodoni Moda
  Handwriting/Script: Dancing Script, Pacifico, Satisfy, Great Vibes, Caveat, Sacramento
  Monospace/Tech: Space Mono, JetBrains Mono, Fira Code, Source Code Pro
  Khmer: Battambang, Siemreap

== TEMPLATES (first blueprint for a new site) ==
When the user starts from a template, your FIRST blueprint MUST match that template's structure: same
section order, types, style numbers, subtypes, fonts, animation, and color palette. The onboarding answers
arrive in the first message — replace placeholder text/images with the user's real content; keep the structure.

ecommerce — Online Shop. Fonts: title=Barlow Condensed, body=Mulish. animation=slide-up. accent=#3b82f6.
  Hero(1) style2 → About(2) style2 → Gallery(3) style1 subtype=product → Testimonials(10) style7
  → FAQ(9) style1 → Footer(4) style4.  Palette: bg #0f172a, title #f8fafc; About/FAQ bg #ffffff; Testimonials bg #f1f5f9.
creator — Content Creator. Fonts: title=Space Grotesk, body=Inter. animation=blur. accent=#f59e0b.
  Hero(1) style1 → About(2) style2 → Gallery(3) style6 subtype=gallery → Testimonials(10) style7
  → Custom(11) style3 → Footer(4) style2.  Palette: hero/about bg #18181b; gallery/testimonials bg #fafaf9; custom bg #f59e0b; footer #09090b.
portfolio — Portfolio. Fonts: title=Outfit, body=Plus Jakarta Sans. animation=none. accent=#111827.
  Hero(1) style3 (NO image) → About(2) style1 → Gallery(3) style11 subtype=product → Custom(11) style2
  → Testimonials(10) style7 → Footer(4) style1.  Palette: hero bg #ffffff; about/testimonials bg #f9fafb; custom bg #111827.
  NOTE: the gallery here is product cards — send subtype "product" (template label "project" → always emit "product").
publisher — Publisher. Fonts: title=Playfair Display, subtitle=Source Sans 3, body=Lora. animation=slide-left. accent=#b5232a.
  Hero(1) style5 → About(2) style7 → Blog(7) style6 → Gallery(3) style3 subtype=gallery → Team(8) style4
  → Ranking(12) style1 → Footer(4) style5.  Palette: bg #faf6ef, title #1c1a17; About/Team bg #fdf9f4; Gallery bg #1c1a17 (title #faf6ef); footer #1c1a17.
"""


@router.post("/builder/chat", response_model=BuilderChatResponse, dependencies=[Depends(_verify_api_key)])
async def builder_chat(request: ChatRequest):
    logger.info("Model: %s | user=%s session=%s community=%s", grok.BUILDER_MODEL, request.user_id, request.session_id, request.community_id)
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
    _VALID_ANIMATIONS = {"none", "fade", "slide-up", "slide-left", "blur"}
    try:
        reply: str = data.get("reply") or ""
        raw_blueprint = data.get("blueprint")
        raw_patches = data.get("patches")
        raw_uploads = data.get("uploads_needed")
        raw_animation = data.get("animation_style")
        animation_style: str | None = (
            raw_animation if isinstance(raw_animation, str) and raw_animation in _VALID_ANIMATIONS else None
        )
        raw_font = data.get("font")
        font: str | None = (
            raw_font.strip()[:64] if isinstance(raw_font, str) and raw_font.strip() else None
        )
    except AttributeError as e:
        logger.error("Envelope extract error: %s | Data: %s", str(e), data)
        raise HTTPException(status_code=422, detail=f"AI returned unexpected format: {str(e)}")

    def _normalize_blueprint(raw: dict) -> dict:
        """Fix common AI field name mismatches before Pydantic validation."""
        # Clamp animation_style to known values
        valid_animations = {"none", "fade", "slide-up", "slide-left", "blur"}
        anim = str(raw.get("animation_style") or "fade").lower()
        raw["animation_style"] = anim if anim in valid_animations else "fade"
        raw.setdefault("template", 1)
        raw.setdefault("font", "")

        for section in raw.get("content", []):
            section_type = normalize_section_type(section.get("type"))
            if section_type:
                section["type"] = section_type
            # GALLERY: normalize photo/product subtype ('project' -> 'product', infer if absent).
            subtype = normalize_gallery_subtype(section)
            if subtype is not None:
                section["section_subtype"] = subtype
            style, style_changed = normalize_style(section_type, section.get("style"), subtype)
            if style_changed:
                logger.warning(
                    "Adjusted invalid blueprint style for section=%s subtype=%s from=%s to=%s based on backend canonical map",
                    section_type,
                    subtype,
                    section.get("style"),
                    style,
                )
            section["style"] = style
            # Always clear bg_image_url — it's user-uploaded, not AI-generated
            section["bg_image_url"] = ""
            section.setdefault("bg_image_opacity", 0.5)
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

    # Surface the blueprint's font at top level too, mirroring animation_style handling.
    if font is None and blueprint is not None and blueprint.font:
        font = blueprint.font

    return BuilderChatResponse(
        reply=reply,
        animation_style=animation_style,
        font=font,
        blueprint=blueprint,
        patches=patches,
        uploads_needed=uploads_needed,
        styles_selected=styles_selected,
        user_id=request.user_id,
        session_id=request.session_id,
    )
