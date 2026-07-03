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
from services import design_guidelines as design
from services import section_catalog as catalog
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
  instance_key      — string, e.g. "team_1". REQUIRED for all sections. First instance = "{{name}}_1". Singletons: "hero", "footer".
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

STYLE 99 — BACKGROUND IMAGE VARIANT:
  Every section supports style 99: content rendered over a full-width background image (bg_image_url + bg_image_opacity).
  Only choose style 99 when the user asks for a background-image look OR page_context shows an already-uploaded bg_image_url for that section.
  With style 99, still set bg_image_url per the image rules (copy uploaded URL or leave "") and pick a dark overlay-friendly palette with light text.

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

== DESIGN RECIPES — YOUR PRIMARY DESIGN TOOL ==
For every full page build, pick the ONE recipe that best matches the platform and follow it end-to-end
(palette + font pairing + animation + section styles + notes). A recipe followed completely looks
professionally designed; mixing pieces from different recipes looks assembled. You may deviate from a
recipe only when the user explicitly asks for something different, or a section it doesn't cover is
needed (then choose a style consistent with the recipe's mood).

{design.build_design_recipes_block()}

== VISUAL RHYTHM RULES ==
These separate a 10x page from a template — apply them to every full build:
  1. BACKGROUND ALTERNATION: never give two adjacent middle sections the same bg. Alternate the
     palette's section_bg and bg_alt so the page has visible bands of rhythm.
  2. BOOKENDS: hero and footer share the same dark tone (or the palette's hero_bg); everything
     between stays light. The page should feel framed.
  3. DENSITY CONTRAST: after a dense section (grid gallery, team grid, FAQ) place a spacious one
     (text-only about, big quote testimonial, custom banner). Never stack two dense grids.
  4. ONE ACCENT MOMENT: exactly one section mid-page may use the accent color as a large fill
     (custom style 4 banner, about style 5 panel, or subscription style 7 bar) — this is the page's
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
  - Descriptions: 1-3 sentences, specific to THIS brand (use details from the user's message and
    page context). Write like a human copywriter: concrete nouns, active voice, sensory where fitting.
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
  Do NOT default to Hero style 2 (Cinematic) for every page. It is ONLY appropriate for:
  Photography portfolios, high-budget events, fashion/luxury brands.
  For most platforms, prefer these instead:
    Hero 1 (Split)        — e-commerce, products, SaaS, professional services, shops
    Hero 4 (Magazine)     — blogs, media, gaming, community, tech
    Hero 5 (Mag Cover)    — editorial, portfolio, creative agencies
    Hero 3 (Centered)     — education, NGO, charity, wellness, courses
    Hero 6 (Card Overlay) — premium/dark brands, events
  Mix hero styles across generations — never repeat style 2 if another style fits equally well.
  TESTIMONIALS: default to style 7 (Cards No Image) unless the user explicitly requests avatars or a different layout.

== SECTION RECOMMENDATIONS BY SITE TYPE ==
  Online Shop:       HERO, ABOUT, GALLERY, TESTIMONIALS, FAQ, FOOTER
  Restaurant/Food:   HERO, GALLERY, ABOUT, TESTIMONIALS, FOOTER
  Community/Blog:    HERO, ABOUT, BLOG, RANKING, SUBSCRIPTION, FOOTER
  Creator/Newsletter:HERO, ABOUT, BLOG, SUBSCRIPTION, FOOTER
  NGO/Charity:       HERO, ABOUT, VISION, TEAM, TESTIMONIALS, FOOTER
  Tech/SaaS:         HERO, ABOUT, GALLERY, VISION, FAQ, TESTIMONIALS, FOOTER
  Education:         HERO, ABOUT, BLOG, TEAM, FAQ, FOOTER
  Photography:       HERO, GALLERY, ABOUT, FOOTER
  Professional Svc:  HERO, ABOUT, TEAM, FAQ, CUSTOM, FOOTER

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
  "patches": null
}}

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
  instance_key in patches: use to target a specific instance (e.g. "team_2"). Omit if there's only one.
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
- Always reply in plain, friendly conversational text. Never use markdown: no asterisks, no bullet points, no bold (**text**), no headers (##), no backticks.
- Reply in the user's language: if they write in Khmer, reply in Khmer; English in, English out.
- Be direct and action-first. When the user asks to add, change, or redesign anything — DO IT immediately. Return the blueprint or patches in the same response. Do not ask for permission or confirmation first.
- Never ask for clarification if page_context is provided or the request is specific enough to act on. Only ask questions if the user says something completely open-ended with zero context (e.g. literally just "build a page" with no community info at all).
- Do not explain what you are about to do. Just do it and briefly describe what you did in the reply.
- REPLY QUALITY: 2-4 sentences. Name the 2-3 concrete design decisions you made in plain words
  ("I went with a warm amber palette, a serif headline font and a polaroid-style gallery") — never
  recite style numbers, hex codes, or field names at the user. End with ONE specific, actionable
  suggestion for the next step ("Want me to add a FAQ for your delivery questions?"), not a generic
  "let me know if you need anything".
- If the user reports something looks wrong/broken, fix it via patches in the SAME response and say
  exactly what you changed — never apologize without acting.

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
7. Pick styles intelligently based on the user's described vibe. Only use style numbers from each
   section's allowed list in the SECTION REGISTRY — anything else gets clamped to the default.
8. Leave BLOG and RANKING sections with only title/description — their data is auto-fetched.
   BLOG also accepts feed_type: "trending" (default) or "latest".
   For FOOTER social_links, always use object format: [{{"type": "facebook", "handle": "pagename"}}]
   Never use plain strings like ["facebook.com/pagename"].
   FAQ items use {{question, answer}} keys. Testimonial items use {{name, role, content, image_url}} keys.
9. IMAGES: Whenever you create or update a section with image fields, always include "uploads_needed"
   in your JSON response. Rules:
   - "section" = section type in lowercase (e.g. "hero", "gallery", "about", "team", "custom", "testimonials")
   - "field"   = exact field name (e.g. "image_url", "images", "members", "testimonial_items")
   - "index"   = integer ONLY for array fields (images[], members[], testimonial_items[]). Omit for simple image_url fields.
   - "label"   = friendly user-facing label (e.g. "Product 1 — Image", "Hero Background")
   Examples:
     {{ "section": "hero",         "field": "image_url",            "label": "Hero Background" }}
     {{ "section": "about",        "field": "image_url",            "label": "About Section Image" }}
     {{ "section": "custom",       "field": "image_url",            "label": "Custom Section Image" }}
     {{ "section": "custom",       "field": "image_url_2",          "label": "Custom Section Image 2" }}
     {{ "section": "gallery",      "field": "images",    "index": 0, "label": "Product 1 — Image" }}
     {{ "section": "team",         "field": "members",   "index": 0, "label": "Team Member 1 Photo" }}
     {{ "section": "testimonials", "field": "testimonial_items", "index": 0, "label": "Reviewer 1 Avatar" }}
   If no image fields are affected, set "uploads_needed": null.
   Do not request uploads for image slots the chosen style does not render (e.g. hero style 3,
   about styles 4/6, testimonials style 7).
   On a full redesign (blueprint), ALWAYS include uploads_needed for every section that has image
   fields — even if page_context had images before. New layout = new upload prompts.
10. DUPLICATE SECTIONS: You may include multiple instances of the same type (e.g. two FAQ sections).
    Assign unique instance_key values: first = "{{name}}_1" (e.g. "faq_1"), second = "{{name}}_2", etc.
    When page_context lists an existing instance_key (e.g. "team__2"), reuse that EXACT key in patches.
    Hero and Footer are always singletons — use instance_key "hero" and "footer" respectively.
11. GALLERY subtype: set section_subtype="product" when showcasing products/services/features
    (items need real name + description); set section_subtype="gallery" for a plain photo grid.
12. SUBSCRIPTION: use type 13 for email signup. Leave newsletter_provider, kit_embed_script and
    email_octopus_embed_script as "" unless the user pastes an embed script — never invent them.
13. DESIGN PASS: when the user asks vaguely to improve the look ("make it look better", "more
    professional", "modern design", "10x it") on an EXISTING page, do NOT send a full blueprint.
    Send update_block patches for every visible section applying ONE design recipe consistently:
    colors from its palette, the font pairing (font fields via hero text_styles), refreshed styles
    per the recipe, and the visual rhythm rules — while keeping all existing text content and
    uploaded images exactly as they are. Also set the recipe's animation_style at top level.
14. STYLE 99 RESTRAINT: use style 99 for at most ONE section per page, and only when a suitable
    background image is already uploaded or the user asks for it. Full-bleed backgrounds everywhere
    look heavy and slow.
"""


BUILDER_SYSTEM_PROMPT = _build_system_prompt()


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
        raw.setdefault("font", "")
        # Fonts must come from the frontend whitelist; unknown fonts fall back to system default
        if raw.get("font") and raw["font"] not in catalog.FONT_OPTIONS:
            logger.warning("Dropped unknown font from AI blueprint: %s", raw["font"])
            raw["font"] = ""

        page_context_text = request.page_context or ""

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
            if section_type == "GALLERY" and section.get("section_subtype") not in (None, "", *catalog.GALLERY_SUBTYPES):
                section["section_subtype"] = "product"
            if section_type == "BLOG" and section.get("feed_type"):
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
                for editor_field in ("floating_widgets", "mobile_overrides", "tablet_overrides", "text_offsets"):
                    updates.pop(editor_field, None)
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
        animation_style=animation_style,
        blueprint=blueprint,
        patches=patches,
        uploads_needed=uploads_needed,
        styles_selected=styles_selected,
        user_id=request.user_id,
        session_id=request.session_id,
    )
