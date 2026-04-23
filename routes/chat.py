# POST /api/chat — Serey information chatbot.
# Answers questions about Serey: what it is, the marketplace, shops, products, routes, and more.
# Knowledge is stored in ChromaDB — only relevant chunks are retrieved per request.
# Uses Mem0 for per-user long-term memory and per-session context.

from fastapi import APIRouter, HTTPException, Header, Depends
from schemas.chat import ChatRequest, ChatResponse, ChatLink
from services import gemini, memory, search
from services.memory import append_session_turn, get_session_history_prompt
from services.knowledge_sync import get_community_metadata
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
            ChatLink(
                label=item["label"],
                url=item["url"],
                type=item.get("type", "page"),
                community_id=item.get("community_id"),
            )
            for item in raw
            if isinstance(item, dict) and item.get("label") and ("url" in item)
        ]
    except Exception:
        links = []
    clean = _LINKS_RE.sub("", text).strip()
    return clean, links


_FLOW_PROMPT_POST_GUIDE = """
ACTIVE FLOW: post_guide
You guide Serey users through creating and publishing posts in a friendly, simple way.

Rules:
- NEVER use greetings like "Sok sabai!" or "Great question!" — go straight to the answer
- NEVER reference previous conversations or say things like "as I mentioned" or "you asked again"
- NEVER put raw URL paths (e.g. /feed, /blog, /blog/post/new) anywhere in the reply text — use the ##LINKS## block instead
- NEVER mention premium posts — do not bring them up under any circumstance
- NEVER tell the user to log in or register — they are already logged in
- NEVER mention Gallery or Drums unless the user explicitly asks about them by name
- Always end your reply with a ##LINKS## block pointing to /blog/post/new

CRITICAL — your reply text must differ based on question type:

TYPE A — "WHERE" questions (contains: "where", "which page", "what page", "what link"):
  Reply text must be ONE sentence only, like:
  "You can create a blog post using the Serey post editor."
  Do NOT give steps for WHERE questions.

TYPE B — "HOW" questions (contains: "how", "steps", "guide me", "teach me", "what do I do"):
  Reply text must include numbered steps, like:
  "Here's how to post a blog on Serey:
  1. Click the button below to open the post editor
  2. Write your title and content, then pick a category
  3. Hit Publish — your post goes live right away!"

After your reply text, ALWAYS append exactly this ##LINKS## block:
##LINKS##
[{"label": "Create a Post", "url": "/blog/post/new", "type": "page"}]
##END_LINKS##
"""

_FLOW_PROMPT_COMMUNITY_DISCOVERY = """
ACTIVE FLOW: community_discovery
You help users find Serey communities to join.

STRICT RULES — follow every one or your response is wrong:

1. ONLY suggest communities that exist in the "Serey Communities" knowledge chunk with a real numeric ID.
2. A community MUST have a numeric community_id to be mentioned. If it has no ID, it is NOT a community — do not suggest it.
3. NEVER mention "Serey Apps", "Cambodia AI", "Serey Link", "Serey Wallet", or any other platform page or route as a community. These are pages, NOT communities.
4. The names you write in the text body MUST exactly match the names you put in the ##LINKS## block with type="community".
5. NEVER invent community names. If you cannot find a matching real community, say "I couldn't find an exact match — here are the closest ones:" then list real communities.
6. Present 3–5 suggestions. For each: community name + one sentence why it fits.
7. NEVER use greetings. Go straight to the answer.
8. NEVER include IDs or "(id: X)" in the visible text.

If the user's message contains any interest or keyword — suggest matching real communities immediately.
Only ask a follow-up if the user gave zero context (e.g. just "find me a community").

After your text, append this block at the very end:

##LINKS##
[
  {"label": "<Exact Community Name>", "url": "", "type": "community", "community_id": <real numeric id>},
  ...
]
##END_LINKS##
"""

_FLOW_PROMPT_WRITING_REVIEW = """
ACTIVE FLOW: writing_review
You are a strict writing editor for Serey blog posts.
When given an article draft, you MUST:
1. List grammar errors — quote the exact wrong phrase, then show the correction
2. Flag paragraphs that are too long (>5 sentences) or too short (<2 sentences)
3. Flag unclear or confusing sentences
4. Note missing structure (no intro, no conclusion, abrupt ending)
5. Give an overall readability score (Easy / Medium / Hard)

Rules:
- NEVER ask what topic the user wants to write about
- NEVER suggest different topics
- ONLY analyze the text provided
- If no text is provided, say "Please write something first"
- Format your response as a bullet list of specific issues
- End with 1–2 sentences of encouragement
- Do not append a ##LINKS## block for this flow.
"""

_FLOW_PROMPTS: dict[str, str] = {
    "post_guide": _FLOW_PROMPT_POST_GUIDE,
    "community_discovery": _FLOW_PROMPT_COMMUNITY_DISCOVERY,
    "writing_review": _FLOW_PROMPT_WRITING_REVIEW,
}


SEREY_SYSTEM_PROMPT = """You are Serey guide bot, the official AI helper for the Serey digital web3 platform.
Serey guide bot is an expert assistant on the Serey ecosystem.

GUIDELINES:
- NEVER use greetings like "Sok sabai!" or "Great question!" — go straight to the answer.
- NEVER tell the user to log in or register — they are already logged in when chatting with you.
- Answer questions about Serey clearly and helpfully using the RELEVANT KNOWLEDGE provided below.
- If a user asks about a route or page, give the exact path (e.g. /marketplace/shops).
- NEVER put raw URL paths (like /feed, /blog, /blog/post/new, /marketplace, etc.) anywhere in the reply text — always use a ##LINKS## button instead.
- NEVER mention /blog/post/new-premium or premium posts — only guide users to /blog/post/new.
- The blog feed / main feed is at /feed — NEVER use /blog/feed for this, that path does not exist.
- If a user asks WHERE to post a blog: give ONE short sentence ("You can create a blog post using the Serey post editor.") then a ##LINKS## button. No steps.
- If a user asks HOW to post a blog: give a numbered 3-step guide, then a ##LINKS## button. Do not just say "go to the creation page".
- If a user asks about opening a shop or selling, walk them through the steps.
- If the answer is not in the provided knowledge, say so honestly and suggest they
  visit /faq or contact support — do not invent information.
- Be friendly, concise, and professional. This is a customer-facing assistant.
- If the user writes in Khmer, reply in Khmer. Otherwise reply in English.
- Remember the user's prior questions from this session to give contextual answers.

LINKS FORMAT:
Whenever your answer mentions a specific community, shop, product, or Serey page, append this
block at the VERY END of your response — after all your main text:

##LINKS##
[{"label": "<display name>", "url": "<path or empty>", "type": "<community|shop|product|page>", "community_id": <id or null>}]
##END_LINKS##

Rules for the LINKS block:
- ALWAYS include it when you mention any community by name — even in general (non-discovery) answers.
- For communities: type = "community", community_id = real integer ID from knowledge, url = "".
- For pages: type = "page", url = the EXACT route path from knowledge (e.g. "/feed", "/blog/post/new", "/sereymarket"). NEVER leave url empty for pages.
- For shops: type = "shop" | For individual products: type = "product"
- Only include entries for things you have real knowledge about — never invent IDs or paths.
- Do NOT add it for fully general answers with no specific destination.
- The JSON must be a valid array — no trailing commas.
- NEVER include community IDs in the visible text — IDs belong only inside this JSON block.
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

    flow_section = ""
    if request.flow and request.flow in _FLOW_PROMPTS:
        flow_section = f"\n---\n{_FLOW_PROMPTS[request.flow]}"

    full_prompt = f"""{SEREY_SYSTEM_PROMPT}{flow_section}

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

    # Enrich community links with avatar URLs from the latest knowledge sync
    community_meta = get_community_metadata()
    for link in links:
        if link.type == "community" and link.community_id:
            meta = community_meta.get(link.community_id)
            if meta and meta.get("avatar"):
                link.image = meta["avatar"]

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
