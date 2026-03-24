# Core POST /generate-blueprint endpoint.
# Orchestrates ChromaDB retrieval, Mem0 memory, Gemini generation, and Pydantic validation.

from fastapi import APIRouter, HTTPException
from schemas.requests import BuilderRequest
from schemas.blueprint import PageBlueprint
from services import gemini, memory, search
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an expert UI architect. Your job is to generate a JSON blueprint for a web page.

RULES:
1. You MUST only use components from the "Available Components" list below.
2. Every component's props MUST exactly match the prop definitions listed.
3. You MUST return ONLY valid JSON — no markdown, no backticks, no explanation outside the JSON.
4. The JSON must match this exact schema:
   {
     "page_title": string,
     "components": [ { "component": string, "props": object } ],
     "reasoning": string
   }
5. Always include a Navbar at the top and a Footer at the bottom unless explicitly told not to.
6. Use the user's preferences from memory to personalize choices (colors, style, tone).
"""


@router.post("/generate-blueprint", response_model=PageBlueprint)
async def generate_blueprint(request: BuilderRequest):
    # 1. Retrieve relevant components from ChromaDB
    try:
        relevant_components = search.search_components(request.prompt, n_results=request.n_components)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    components_context = json.dumps(relevant_components, indent=2)

    # 2. Retrieve memories from Mem0
    long_term_memory = memory.get_user_preferences(request.user_id, request.prompt)
    short_term_memory = memory.get_session_context(request.session_id, request.prompt)

    # 3. Build the full prompt
    full_prompt = f"""
{SYSTEM_PROMPT}

---

AVAILABLE COMPONENTS (use ONLY these):
{components_context}

---

USER LONG-TERM PREFERENCES:
{long_term_memory}

CURRENT SESSION CONTEXT:
{short_term_memory}

---

USER REQUEST:
"{request.prompt}"

Generate the JSON blueprint now:
"""

    # 4. Call Gemini
    try:
        raw_json = gemini.generate(full_prompt)
    except Exception as e:
        logger.error("Gemini API error: %s", str(e))
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")

    # 5. Parse and validate with Pydantic
    try:
        data = json.loads(raw_json)
        blueprint = PageBlueprint(**data)
    except json.JSONDecodeError as e:
        logger.error("JSON decode error from AI: %s | Raw: %s", str(e), raw_json[:500])
        raise HTTPException(
            status_code=422,
            detail=f"AI returned invalid JSON: {str(e)}",
        )
    except Exception as e:
        logger.error("Pydantic validation error: %s | Data: %s", str(e), str(raw_json)[:500])
        raise HTTPException(
            status_code=422,
            detail=f"AI returned wrong structure: {str(e)}",
        )

    # 6. Save interaction to memory (non-critical)
    try:
        memory.save_interaction(
            user_id=request.user_id,
            session_id=request.session_id,
            content=(
                f"User asked: '{request.prompt}'. "
                f"AI generated a page called '{blueprint.page_title}' "
                f"with components: {[c.component for c in blueprint.components]}"
            ),
        )
    except Exception as e:
        logger.warning("Memory save failed (non-critical): %s", str(e))

    return blueprint


@router.get("/components")
async def list_components():
    """Returns all indexed component names. Useful for frontend debugging."""
    try:
        names = search.get_all_component_names()
        return {"components": names}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
