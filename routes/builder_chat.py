# POST /api/builder/chat — Conversational AI page builder.
# The user describes or iterates on a page in plain language.
# The AI responds with a text reply AND an updated PageBlueprint (or null if not applicable).
# The blueprint is ready to be consumed directly by the Next.js DynamicRenderer.

from fastapi import APIRouter, HTTPException, Header, Depends
from schemas.chat import ChatRequest, BuilderChatResponse
from schemas.blueprint import PageBlueprint
from services import gemini, search
from services.memory import append_session_turn, get_session_history_prompt
import json
import logging
import os

router = APIRouter()
logger = logging.getLogger(__name__)

_CHAT_API_KEY = os.getenv("CHAT_API_KEY", "")


def _verify_api_key(x_serey_api_key: str = Header(default="")) -> None:
    """Dependency: reject requests with a missing or wrong X-Serey-API-Key header.
    Skipped entirely when CHAT_API_KEY is not set (local dev convenience)."""
    if _CHAT_API_KEY and x_serey_api_key != _CHAT_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: invalid API key")

BUILDER_SYSTEM_PROMPT = """You are an expert AI page builder assistant for the Serey community landing pages.
Your job is to help users design landing pages through natural conversation.

We use a specific numeric block structure:
- `type: 1` = Hero Section (uses title, description, image_url)
- `type: 2` = About Section (uses title, description, image_url)
- `type: 3` = Gallery Section (uses a property `images` which is an array of strings representing image URLs)
- `type: 4` = Footer/Contact Section (uses title, description, phone, and a list of social_links)

STYLE GUIDELINES (Use these to intelligently suggest styles):
- `style: 1` is generally left-aligned, spacious, and professional.
- `style: 2` is generally centered, bold, and modern.
Pick the best style based on the user's vibe, or ask them what they prefer.

RULES:
1. Always return ONLY valid JSON — no markdown, no extra text outside the JSON.
2. Your response MUST match this exact schema:
   {
     "reply": "friendly conversational message to the user",
     "blueprint": {         // Use ONLY when defining the initial page or making massive structural changes
       "community_id": 123,
       "template": 1,
       "content": [ 
         { 
           "type": 1, 
           "style": 1, 
           ...
         } 
       ]
     } OR null,             // null if generating patches or just answering a question
     "patches": [           // Use ONLY when updating an existing layout (e.g. changing title, replacing image)
       {
         "action": "update_block", // "update_block" | "add_block" | "delete_block"
         "type": 1,                // The numeric block type to target (e.g. 1 for Hero)
         "updates": {              // The specific keys to update
           "title": "New Hero Title"
         }
       }
     ] OR null              // null if creating a full blueprint or just answering a question
   }
3. Always generate a Hero block (type 1) at the top and a Footer block (type 4) at the bottom.
4. PROACTIVE UX: If a user makes a vague request (e.g., "build my page"), do NOT guess blindly. Set blueprint to null and ask them guiding questions (e.g., "What is the main goal of your community? Do you prefer a modern centered look or a professional left-aligned look?").
5. Answer naturally in the 'reply' field. Personalise styles based on session context.
"""


@router.post("/builder/chat", response_model=BuilderChatResponse, dependencies=[Depends(_verify_api_key)])
async def builder_chat(request: ChatRequest):
    # 1. Retrieve relevant components from ChromaDB (reduced n_results to save tokens)
    try:
        relevant_components = search.search_components(request.message, n_results=4)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Token Optimization: Extract ONLY the minimum required fields for the AI
    # (name, type, style) instead of dumping full embeddings and huge HTML properties
    lightweight_components = []
    for comp in relevant_components:
        lightweight_components.append({
            "name": comp.get("name", "Unknown Component"),
            "type": comp.get("type"),
            "style": comp.get("style", 1)
        })

    components_context = json.dumps(lightweight_components, separators=(',', ':'))

    # 2. Retrieve session history
    session_history = get_session_history_prompt(request.session_id)
    history_section = (
        f"CONVERSATION HISTORY (this session):\n{session_history}"
        if session_history
        else "CONVERSATION HISTORY: (no prior turns in this session)"
    )

    # 3. Build the full prompt
    community_ctx = f"COMMUNITY ID: {request.community_id} (you MUST include this exact value in the blueprint's community_id field)" if request.community_id else ""
    full_prompt = f"""{BUILDER_SYSTEM_PROMPT}

---

AVAILABLE COMPONENTS (use ONLY these):
{components_context}

---

{community_ctx}

{history_section}

---

USER: {request.message}

Respond with valid JSON now:
"""

    # 4. Call Gemini in JSON mode
    try:
        raw_json = gemini.generate(full_prompt)
    except Exception as e:
        logger.error("Gemini builder_chat error: %s", str(e))
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")

    # 5. Parse the outer {reply, blueprint, patches} envelope
    try:
        data = json.loads(raw_json)
        reply: str = data.get("reply", "...")
        raw_blueprint = data.get("blueprint")
        raw_patches = data.get("patches")
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error("Builder chat envelope parse error: %s | Raw: %s", str(e), raw_json[:500])
        raise HTTPException(
            status_code=422,
            detail=f"AI returned unexpected format: {str(e)}",
        )

    # 6. Validate blueprint or patches only if the AI included them
    blueprint = None
    if raw_blueprint:
        from schemas.blueprint import PageBlueprint
        try:
            blueprint = PageBlueprint(**raw_blueprint)
        except Exception as e:
            logger.warning(
                "Blueprint validation failed (returning reply only): %s | Data: %s",
                str(e),
                str(raw_blueprint)[:300],
            )
            # Non-fatal: still return the reply with blueprint=None so the user is not blocked
            reply += "\n\n⚠️ (Note: the page layout could not be applied — please rephrase your request.)"

    patches = None
    if raw_patches and isinstance(raw_patches, list):
        from schemas.blueprint import PatchCommand
        try:
            patches = [PatchCommand(**p) for p in raw_patches]
        except Exception as e:
            logger.warning("Patches validation failed: %s | Data: %s", str(e), str(raw_patches)[:300])
            reply += "\n\n⚠️ (Note: the specific updates could not be applied.)"

    # 7. Save this turn to session history
    try:
        saved_reply = reply
        if blueprint is not None and getattr(blueprint, 'template', None) and getattr(blueprint, 'content', None):
            saved_reply += f"\n[Generated layout template {blueprint.template} with {len(blueprint.content)} sections]"
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
        user_id=request.user_id,
        session_id=request.session_id,
    )
