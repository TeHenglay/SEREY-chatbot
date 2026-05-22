# POST /api/generate-blueprint — One-shot V2 landing page blueprint generation.
# Accepts a prompt + community_id and returns a complete PageBlueprint ready
# to POST to /api/v2/landing-pages.

import asyncio
from fastapi import APIRouter, HTTPException
from schemas.requests import BuilderRequest
from schemas.blueprint import PageBlueprint
from services import grok, memory
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert AI page builder for Serey community landing pages (V2).
Generate a complete landing page JSON blueprint from the user's description.

== SECTION REGISTRY ==
Each page is a JSON array of section objects. Available section types:

CORE:
  HERO        — title, subtitle, description, image_url. Styles 0-6.
  ABOUT       — title, description, image_url. Styles 1-8.
  GALLERY     — title, description, images[{image_url,name,description}]. Styles 1-16.
  FOOTER      — title, description, phone, email, location, logo_url, social_links[{type,handle}]. Styles 1-3.

OPTIONAL:
  VIDEO       — title, description, videos[{url,title,thumbnail}].
  VISION      — title, description, goals_title, goals_description, vision_title, vision_description, mission_title, mission_description. Styles 1-6.
  BLOG        — title, description only (data auto-fetched).
  TEAM        — title, description, members[{name,role,image_url}].
  FAQ         — title, faq_items[{q,a}].
  TESTIMONIALS— title, testimonial_items[{name,role,quote,image_url}] (max 6).
  CUSTOM      — title, description, button_label, button_url, image_url, image_url_2. Styles 1-6.
  RANKING     — title, description only (data auto-fetched).

== SECTION RECOMMENDATIONS BY SITE TYPE ==
  Online Shop:     HERO, ABOUT, GALLERY, TESTIMONIALS, FAQ, FOOTER
  Restaurant/Food: HERO, GALLERY, ABOUT, TESTIMONIALS, FOOTER
  Community/Blog:  HERO, ABOUT, BLOG, RANKING, FOOTER
  NGO/Charity:     HERO, ABOUT, VISION, TEAM, TESTIMONIALS, FOOTER
  Tech/SaaS:       HERO, ABOUT, GALLERY, VISION, FAQ, TESTIMONIALS, FOOTER
  Education:       HERO, ABOUT, BLOG, TEAM, FAQ, FOOTER
  Photography:     HERO, GALLERY, ABOUT, FOOTER

== COLOR DEFAULTS ==
  title: "#0f3460"  accent: "#2b45a8"  body: "#444444"  bg: "#ffffff"
  Hero accent default: "#c0392b"

== STYLE GUIDE ==
  Clean/Minimal:  Hero 1, About 1, Gallery 2,  Custom 3
  Cinematic/Bold: Hero 2, About 7, Gallery 4,  Custom 4
  Magazine:       Hero 5, About 4, Gallery 13, Custom 6
  Dark/Dramatic:  Hero 6, About 8, Gallery 10, Custom 4

== RULES ==
1. Return ONLY valid JSON — no markdown, no backticks, no text outside the JSON.
2. Always include HERO at top and FOOTER at bottom.
3. Set community_id to the value provided in context.
4. Always set image_url to "" — never invent image URLs.
5. Use the user's preferences from memory to personalise color and style choices.
6. Output schema:
{
  "community_id": <integer>,
  "content": [ ...section objects... ]
}
"""


@router.post("/generate-blueprint", response_model=PageBlueprint)
async def generate_blueprint(request: BuilderRequest):
    # 1. Retrieve memories
    long_term_memory = memory.get_user_preferences(request.user_id, request.prompt)
    short_term_memory = memory.get_session_context(request.session_id, request.prompt)

    # 2. Build prompt
    full_prompt = f"""COMMUNITY ID: {getattr(request, 'community_id', 0)} — use this exact integer in community_id

USER LONG-TERM PREFERENCES:
{long_term_memory}

CURRENT SESSION CONTEXT:
{short_term_memory}

---

USER REQUEST:
"{request.prompt}"

Generate the JSON blueprint now:
"""

    def _clean_raw(raw: str) -> str:
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[-1]
            if stripped.endswith("```"):
                stripped = stripped[: stripped.rfind("```")]
        return stripped.strip()

    # 3. Call Grok
    try:
        raw_json = await asyncio.to_thread(grok.generate_builder, full_prompt, SYSTEM_PROMPT)
    except Exception as e:
        logger.error("Grok API error: %s", str(e))
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")

    # 4. Parse and validate
    try:
        cleaned = _clean_raw(raw_json)
        if not cleaned:
            raise ValueError("Model returned empty content")
        data = json.loads(cleaned)
        blueprint = PageBlueprint(**data)
    except json.JSONDecodeError as e:
        logger.error("JSON decode error from AI: %s | Raw: %s", str(e), raw_json[:500])
        raise HTTPException(status_code=422, detail=f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        logger.error("Pydantic validation error: %s | Data: %s", str(e), raw_json[:500])
        raise HTTPException(status_code=422, detail=f"AI returned wrong structure: {str(e)}")

    # 5. Save interaction to memory (non-critical)
    try:
        section_types = [s.type for s in blueprint.content]
        memory.save_interaction(
            user_id=request.user_id,
            session_id=request.session_id,
            content=(
                f"User asked: '{request.prompt}'. "
                f"AI generated a landing page with sections: {section_types}"
            ),
        )
    except Exception as e:
        logger.warning("Memory save failed (non-critical): %s", str(e))

    return blueprint


@router.get("/components")
async def list_section_types():
    """Returns the available V2 landing page section types."""
    return {
        "section_types": [
            "HERO", "ABOUT", "GALLERY", "FOOTER",
            "VIDEO", "VISION", "BLOG", "TEAM",
            "FAQ", "TESTIMONIALS", "CUSTOM", "RANKING",
        ]
    }
