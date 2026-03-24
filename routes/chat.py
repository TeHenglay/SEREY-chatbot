# POST /api/chat — Serey information chatbot.
# Answers questions about Serey: what it is, the marketplace, shops, products, routes, and more.
# Knowledge is stored in ChromaDB — only relevant chunks are retrieved per request.
# Uses Mem0 for per-user long-term memory and per-session context.

from fastapi import APIRouter, HTTPException, Header, Depends
from schemas.chat import ChatRequest, ChatResponse, ChatLink
from services import gemini, memory, search
from services.memory import append_session_turn, get_session_history_prompt
import json
import re
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

_LINKS_RE = re.compile(r'##LINKS##\s*([\s\S]*?)\s*##END_LINKS##', re.DOTALL)


def _extract_links(text: str) -> tuple[str, list[ChatLink]]:
    """Strip the ##LINKS## block from the reply and parse it into ChatLink objects."""
    match = _LINKS_RE.search(text)
    if not match:
        return text, []
    try:
        raw = json.loads(match.group(1))
        links = [
            ChatLink(label=item["label"], url=item["url"], type=item.get("type", "page"))
            for item in raw
            if isinstance(item, dict) and item.get("label") and item.get("url")
        ]
    except Exception:
        links = []
    clean = _LINKS_RE.sub("", text).strip()
    return clean, links


SEREY_SYSTEM_PROMPT = """You are Soriya, the official AI helper for the Serey digital web3 platform.
Soriya is a helpful Cambodian woman who is an expert on the Serey ecosystem.

GUIDELINES:
- Answer questions about Serey clearly and helpfully using the RELEVANT KNOWLEDGE provided below.
- If a user asks about a route or page, give the exact path (e.g. /marketplace/shops).
- If a user asks about opening a shop or selling, walk them through the steps.
- If the answer is not in the provided knowledge, say so honestly and suggest they
  visit /faq or contact support — do not invent information.
- Be friendly, concise, and professional. This is a customer-facing assistant.
- If the user writes in Khmer, reply in Khmer. Otherwise reply in English.
- Remember the user's prior questions from this session to give contextual answers.

LINKS FORMAT:
Whenever your answer references a specific shop, product, or Serey page that has a known URL
(from the knowledge provided), append this block at the VERY END of your response — after all
your main text:

##LINKS##
[{"label": "<display name>", "url": "<full URL>", "type": "<shop|product|page>"}]
##END_LINKS##

Rules for the LINKS block:
- Only include it when you are mentioning something with a real URL in the knowledge.
- For shops: type = "shop"  |  For individual products: type = "product"  |  For site pages: type = "page"
- Do NOT add it for general informational answers that have no specific destination.
- The JSON must be a valid array — no trailing commas.
"""


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(_verify_api_key)])
async def chat(request: ChatRequest):
    # 1. Semantic search: only fetch knowledge chunks relevant to this question
    relevant_knowledge = search.search_serey_knowledge(request.message, n_results=8)

    # 2. Retrieve long-term preferences from Mem0 (cross-session user preferences)
    long_term_memory = memory.get_user_preferences(request.user_id, request.message)

    # 3. Retrieve short-term history from the in-process local store (synchronous, exact)
    #    This is the fix for within-session recall (e.g. user states their name and AI
    #    forgets it on the very next turn). Unlike Mem0, this is immediate and exact.
    session_history = get_session_history_prompt(request.session_id)

    # 4. Build the full prompt — only relevant knowledge injected, not the whole DB
    history_section = (
        f"CONVERSATION HISTORY (this session — use this to recall what the user told you):\n{session_history}"
        if session_history
        else "CONVERSATION HISTORY: (no prior turns in this session)"
    )

    full_prompt = f"""{SEREY_SYSTEM_PROMPT}

---

RELEVANT KNOWLEDGE (retrieved for this question):
{relevant_knowledge}

---

USER LONG-TERM PREFERENCES (from previous sessions):
{long_term_memory}

{history_section}

---

USER: {request.message}

SEREY ASSISTANT:"""

    # 3. Call Gemini (plain text mode)
    try:
        raw_reply = gemini.generate_text(full_prompt)
    except Exception as e:
        logger.error("Gemini chat error: %s", str(e))
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")

    # 4. Extract links block from reply
    reply, links = _extract_links(raw_reply)

    # 5. Save this turn to the in-process local session history immediately (synchronous).
    #    This ensures the AI remembers everything said in this session on the very next turn.
    append_session_turn(
        session_id=request.session_id,
        user_message=request.message,
        assistant_reply=reply,
    )

    # 6. Also save to Mem0 for long-term cross-session user preferences (non-critical)
    try:
        memory.save_interaction(
            user_id=request.user_id,
            session_id=request.session_id,
            content=f"User: {request.message}\nAssistant: {reply}",
        )
    except Exception as e:
        logger.warning("Failed to save chat memory to Mem0: %s", str(e))

    return ChatResponse(
        reply=reply,
        links=links,
        user_id=request.user_id,
        session_id=request.session_id,
    )
