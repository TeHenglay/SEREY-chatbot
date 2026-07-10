# POST /api/generate-blueprint — One-shot V2 landing page blueprint generation.
# Accepts a prompt + community_id and returns a complete PageBlueprint ready
# to POST to /api/v2/landing-pages.

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from schemas.requests import BuilderRequest
from schemas.blueprint import PageBlueprint
from services import grok, memory
from services import design_guidelines as design
from services import section_catalog as catalog
from services.security import require_serey_origin, verify_api_key
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Section/style/palette knowledge is generated from services/section_catalog.py
# (mirrored from the frontend) so this prompt cannot drift from the validators.
SYSTEM_PROMPT = f"""You are an expert AI page builder for Serey community landing pages (V2).
Generate a complete landing page JSON blueprint from the user's description.

== SECTION TYPE IDs ==
{catalog.build_type_id_block()}

== SECTION REGISTRY ==
Each page is a JSON array of section objects. Available section types (with content fields and allowed style numbers):

{catalog.build_section_registry_block()}

== SECTION RECOMMENDATIONS BY SITE TYPE ==
  Online Shop:     HERO, ABOUT, GALLERY, TESTIMONIALS, FAQ, FOOTER
  Restaurant/Food: HERO, GALLERY, ABOUT, TESTIMONIALS, FOOTER
  Community/Blog:  HERO, ABOUT, BLOG, RANKING, SUBSCRIPTION, FOOTER
  NGO/Charity:     HERO, ABOUT, VISION, TEAM, TESTIMONIALS, FOOTER
  Tech/SaaS:       HERO, ABOUT, GALLERY, VISION, FAQ, TESTIMONIALS, FOOTER
  Education:       HERO, ABOUT, BLOG, TEAM, FAQ, FOOTER
  Photography:     HERO, GALLERY, ABOUT, FOOTER

== FONTS ==
Set the blueprint "font" field to ONE font from this list (or "" for system default):
{catalog.build_fonts_block()}

== CURATED PALETTES — pick one, use the exact hex values ==
{catalog.build_palettes_block()}

== DESIGN RECIPES — pick ONE and follow it end-to-end ==
{design.build_design_recipes_block()}

== FONT PAIRINGS ==
Set "font" to the pairing's body font; put the title font in hero text_styles {{"title_font": "..."}}.
{design.build_font_pairings_block()}

== COLOR KEYS PER SECTION ==
{catalog.build_color_keys_block()}

== RULES ==
1. Return ONLY valid JSON — no markdown, no backticks, no text outside the JSON.
2. Always include HERO at top and FOOTER at bottom.
3. Set community_id to the value provided in context.
4. Always set image_url (and every image field) to "" — never invent image URLs.
5. Use the user's preferences from memory to personalise color and style choices.
6. Only use style numbers from each section's allowed list above.
7. Output schema:
{{
  "community_id": <integer>,
  "content": [ ...section objects... ]
}}
"""


@router.post(
    "/generate-blueprint",
    response_model=PageBlueprint,
    dependencies=[Depends(require_serey_origin), Depends(verify_api_key)],
)
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
