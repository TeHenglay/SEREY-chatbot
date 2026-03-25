# POST /api/builder/chat — Conversational AI page builder for Serey V2 landing pages.
# The user describes or iterates on a page in plain language.
# The AI responds with a text reply AND an updated PageBlueprint (or null if not applicable).
# The blueprint matches the V2 API contract: { community_id, content: [...sections] }

from fastapi import APIRouter, HTTPException, Header, Depends
from schemas.chat import ChatRequest, BuilderChatResponse, UploadNeeded
from schemas.blueprint import PageBlueprint, SectionBlock, PatchCommand
from services import gemini
from services.memory import append_session_turn, get_session_history_prompt
import json
import logging
import os

router = APIRouter()
logger = logging.getLogger(__name__)

_CHAT_API_KEY = os.getenv("CHAT_API_KEY", "")


def _verify_api_key(x_serey_api_key: str = Header(default="")) -> None:
    if _CHAT_API_KEY and x_serey_api_key != _CHAT_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: invalid API key")


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

OPTIONAL (add on demand):
  VIDEO       — Embedded videos: title, description, videos[{url,title,thumbnail}]. Style 1.
  VISION      — Goals/Vision/Mission: title, description, goals_title, goals_description,
                vision_title, vision_description, mission_title, mission_description. Styles 1-6.
  BLOG        — Auto-fetches community posts: title, description only. Style 1.
  TEAM        — Team members: title, description, members[{name,role,image_url}]. Style 1.
  FAQ         — Q&A list: title, faq_items[{q,a}]. Style 1.
  TESTIMONIALS— Customer quotes: title, testimonial_items[{name,role,quote,image_url}] (max 6). Style 1.
  CUSTOM      — Flexible promo: title, description, button_label, button_url, image_url, image_url_2. Styles 1-6.
  RANKING     — Auto-fetches top authors: title, description only. Style 1.

== SECTION OBJECT SHAPE ==
Every section must include:
  type        — string, e.g. "HERO" (REQUIRED)
  style       — integer, e.g. 1 (REQUIRED)
  is_hidden   — boolean, default false (REQUIRED)
  colors      — object with keys: title, accent, body, bg  (plus subtitle for HERO; goal_color, vision_color, mission_color for VISION)

== COLOR DEFAULTS ==
  title:   "#0f3460"    accent: "#2b45a8"    body: "#444444"    bg: "#ffffff"
  Hero accent default: "#c0392b"

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

VISION styles:
  1 = 3 cards with accent icon circles, split layout.
  2 = 3-column colored cards. Each card bg = its color (goal/vision/mission).
  3 = Horizontal icon rows with number on right.
  4 = Numbered steps — dark style.
  5 = Feature grid — icon circle, title, description, centered.
  6 = Split panel — accent-bg column left, list of icon rows right.

FOOTER styles:
  1 = Dark navy — logo + contact left, social icons + copyright bottom strip.
  2 = Light minimal centered — logo, title, contact, social, copyright.
  3 = Dark 3-column grid — logo/tagline, contact, follow-us columns.

== STYLE GUIDE (by personality) ==
  Clean/Minimal:      Hero 1, About 1, Gallery 2,  Custom 3, Footer 2
  Cinematic/Bold:     Hero 2, About 7, Gallery 4,  Custom 4, Footer 1
  Magazine/Editorial: Hero 5, About 4, Gallery 13, Custom 6, Footer 3
  Dark/Dramatic:      Hero 6, About 8, Gallery 10, Custom 4, Footer 1
  Playful/Creative:   Hero 3, About 2, Gallery 9,  Custom 5, Footer 2
  Organized/Corporate:Hero 4, About 3, Gallery 3,  Custom 2, Footer 3
  Photography:        Hero 2, About 5, Gallery 6,  Custom 2, Footer 1
  Product Showcase:   Hero 1, About 4, Gallery 15, Custom 1, Footer 2

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
        "colors": { "title": "#0f3460", "accent": "#c0392b", "subtitle": "#0f172a", "body": "#475569", "bg": "#F9FBFF" }
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
  IMPORTANT: use "add_block" (NOT "update_block") whenever the section doesn't already exist on the page.

OR when just answering a question (no layout change):
{
  "reply": "...",
  "blueprint": null,
  "patches": null
}

== COMMUNICATION RULES ==
- Always reply in plain, friendly conversational text. Never use markdown: no asterisks, no bullet points, no bold (**text**), no headers (##), no backticks.
- When the user asks to add or change something, check page_context first and act immediately — return patches or blueprint right away.
- Never ask for clarification if the answer is already in page_context (e.g. if sections are listed there, you know what exists and what's missing).

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

    full_prompt = f"""{BUILDER_SYSTEM_PROMPT}

---

{community_ctx}

{page_ctx}

{history_section}

---

USER: {request.message}

Respond with valid JSON now:
"""

    # 3. Call Gemini — retry once on malformed JSON
    data = None
    for attempt in (1, 2):
        raw_response = ""
        try:
            raw_response = gemini.generate(full_prompt)
            data = json.loads(raw_response)
            break
        except json.JSONDecodeError as e:
            logger.error("JSON parse error (attempt %d): %s | Raw: %s", attempt, str(e), raw_response[:600])
            if attempt == 2:
                raise HTTPException(status_code=422, detail=f"AI returned malformed JSON after retry: {str(e)}")
        except Exception as e:
            logger.error("Gemini error (attempt %d): %s", attempt, str(e))
            if attempt == 2:
                raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")
    if data is None:
        raise HTTPException(status_code=502, detail="AI service returned no data")
    assert isinstance(data, dict)  # type: narrowing for static analysis

    # 4. Extract envelope fields
    try:
        reply: str = data.get("reply", "...")
        raw_blueprint = data.get("blueprint")
        raw_patches = data.get("patches")
        raw_uploads = data.get("uploads_needed")
    except AttributeError as e:
        logger.error("Envelope extract error: %s | Data: %s", str(e), data)
        raise HTTPException(status_code=422, detail=f"AI returned unexpected format: {str(e)}")

    def _normalize_blueprint(raw: dict) -> dict:
        """Fix common AI field name mismatches before Pydantic validation."""
        for section in raw.get("content", []):
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
    blueprint_failed = False
    if raw_blueprint:
        try:
            blueprint = PageBlueprint(**_normalize_blueprint(raw_blueprint))
        except Exception as e:
            blueprint_failed = True
            logger.error("Blueprint validation failed: %s | Data: %s", str(e), raw_blueprint)
            raise HTTPException(
                status_code=422,
                detail=f"AI returned invalid blueprint structure: {str(e)}",
            )

    # 6. Validate uploads_needed — only keep if blueprint/patches succeeded
    uploads_needed = None
    if not blueprint_failed and raw_uploads and isinstance(raw_uploads, list):
        try:
            uploads_needed = [UploadNeeded(**u) for u in raw_uploads]
        except Exception as e:
            logger.warning("uploads_needed validation failed: %s", str(e))

    # 7. Validate patches (if present)
    patches = None
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
                normalized.append(p)
            patches = [PatchCommand(**p) for p in normalized]
        except Exception as e:
            logger.error("Patches validation failed: %s | Data: %s", str(e), raw_patches)
            raise HTTPException(
                status_code=422,
                detail=f"AI returned invalid patch structure: {str(e)} | Raw patches: {raw_patches}",
            )

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

    return BuilderChatResponse(
        reply=reply,
        blueprint=blueprint,
        patches=patches,
        uploads_needed=uploads_needed,
        user_id=request.user_id,
        session_id=request.session_id,
    )
