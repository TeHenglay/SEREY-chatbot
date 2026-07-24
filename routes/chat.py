# POST /api/chat — Serey information chatbot.
# Answers questions about Serey: what it is, the marketplace, shops, products, routes, and more.
# Knowledge is stored in ChromaDB — only relevant chunks are retrieved per request.
# Uses Mem0 for per-user long-term memory and per-session context.

import asyncio
import json
import logging
import os
import re
import time

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from services.security import require_serey_origin

from schemas.chat import ChatLink, ChatRequest, ChatResponse
from services import grok, memory, search
from services.knowledge_sync import get_community_metadata
from services.memory import append_session_turn, get_session_history_prompt

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response cache — shared across users for common questions.
# Key: (normalized_message, flow). TTL: 5 minutes.
# Only caches the raw Grok reply; link enrichment still runs per-request.
# ---------------------------------------------------------------------------
_CACHE_TTL = 300  # seconds
_response_cache: dict[tuple[str, str], tuple[str, float]] = {}


def _cache_key(message: str, flow: str | None) -> tuple[str, str]:
    normalized = " ".join(message.lower().split())
    return (normalized, flow or "")


def _cache_get(key: tuple[str, str]) -> str | None:
    entry = _response_cache.get(key)
    if entry and (time.monotonic() - entry[1]) < _CACHE_TTL:
        return entry[0]
    if entry:
        del _response_cache[key]
    return None


def _cache_set(key: tuple[str, str], raw_reply: str) -> None:
    # Evict old entries to keep memory bounded (max 200 entries)
    if len(_response_cache) >= 200:
        oldest_key = min(_response_cache, key=lambda k: _response_cache[k][1])
        del _response_cache[oldest_key]
    _response_cache[key] = (raw_reply, time.monotonic())

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
  Then add a blank line and a short line "Here is a quick video walkthrough:" followed on its OWN line by
  this exact full video URL (this https video link IS allowed in the reply text):
  https://storage.serey.io/videos/01KY9E1KDQJ1Z8XYYXSF6HQ32A.mp4

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
6. NEVER append the word "Community" to a community name. Use the exact name as it appears in the knowledge base — no suffixes, no additions.
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

CRITICAL INSTRUCTION — READ THIS FIRST:
Look at the user's message word by word. Decide which of the two modes below applies, then follow ONLY that mode. Do NOT mix modes.

MODE 1 — SUMMARY / MEANING (use this mode when the user asks what the text is about)
  Trigger words: "what is it about", "what is the paragraph about", "what is this about", "summarize", "what does it say", "explain", "what is the topic", "what is the main idea"
  → If the user's message matches any of the above: write 2–3 sentences summarizing the main topic and theme of the text. Do NOT mention grammar, paragraph length, structure, or readability. Do NOT do a writing review.

MODE 2 — WRITING REVIEW (use this mode only when the user asks for feedback on the writing itself)
  Trigger words: "review", "check", "fix", "improve", "feedback", "edit", "grammar", "how is my writing", "is it good"
  → If the user's message matches any of the above: do a full writing analysis:
    1. Grammar errors — quote the exact wrong phrase, then show the correction
    2. Paragraph length issues (>5 sentences is too long, <2 is too short)
    3. Unclear or confusing sentences
    4. Missing structure (no intro, no conclusion, abrupt ending)
    5. Overall readability score: Easy / Medium / Hard
    Format as a bullet list. End with 1–2 sentences of encouragement.

Rules:
- NEVER mix modes. If the user asks what the paragraph is about — give a summary only, not a review.
- NEVER ask what topic the user wants to write about
- NEVER suggest different topics
- ONLY discuss the text provided in the page context or message
- If no text is provided, say "Please write something in the editor first so I can help."
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
- The feed is at /feed — always call it "Feed", NEVER "Main Feed". NEVER use /blog/feed for this, that path does not exist.
- If a user asks WHERE to post a blog: give ONE short sentence ("You can create a blog post using the Serey post editor.") then a ##LINKS## button. No steps.
- If a user asks HOW to post a blog: give a numbered 3-step guide, then a ##LINKS## button. Do not just say "go to the creation page".
- If a user asks about opening a shop or selling, walk them through the steps.
- If the answer is not in the provided knowledge, say so honestly and suggest they
  visit /faq or contact support — do not invent information.
- Be friendly, concise, and professional. This is a customer-facing assistant.
- If the user writes in Khmer, reply in Khmer. Otherwise reply in English.
- Use **bold** markdown for key values and important terms: temperatures, prices, dates, section headings, product names, community names, and critical instructions.
- Remember the user's prior questions from this session to give contextual answers.

TUTORIAL VIDEOS:
Serey has short video tutorials for common tasks. When the user asks HOW to do one of the tasks below, include the matching video link on its OWN line in your reply text, as the full https URL exactly as written, so it plays inline for them. Add a short line before it like "Here is a quick video walkthrough:". These full https://storage.serey.io video links ARE allowed in the reply text; the "no raw URL paths" rule only applies to internal paths that start with "/", not to these video links. Only include a video that matches the user's question, and never invent a video link. The full tutorials page is at /tutorials.
- Publish a blog post: https://storage.serey.io/videos/01KY9E1KDQJ1Z8XYYXSF6HQ32A.mp4
- Buy a Serey plan or subscription: https://storage.serey.io/videos/01KY9E2T3GDM77W1C9XJNTCF5J.mp4
- Set up your Serey Link (link in bio): https://storage.serey.io/videos/01KY9E4N3Q7E5671BEKXBSNF6T.mp4
- Post a podcast: https://storage.serey.io/videos/01KY9E35R59CBNFAZ00JEEEH45.mp4
- Referral link, invite friends and earn: https://storage.serey.io/videos/01KY9E437A9SZTXA90C4BSNPKQ.mp4
- Add a group chat: https://storage.serey.io/videos/01KY9E5BBXVVRY2B3MJNJZHX24.mp4

PRODUCT / SHOP LISTING FORMAT:
When the user asks about featured products, discounted items, products in a shop, or any list of products/items — you MUST:
1. Start with ONE short intro sentence — max 10 words (e.g. "Here are the cheapest products on Serey Marketplace:"). Do NOT mention user memory or prior conversations in this sentence.
2. List EVERY individual item as a bullet point in this exact format:
   • **<actual product name>**: [brief description], **$<price>**[, **X% discount**][, discount expires <date>].
   - Use the real product name — do NOT wrap it in brackets like [name] or [Product Name].
   - Only include the discount expiry if there is a real expiry date. Do NOT say "permanent".
3. Include ALL items from the knowledge — do NOT summarize or group them. List each one separately.
4. After the bullet list, add a ##LINKS## block with one entry per product (type="product") plus a general marketplace link.
5. NEVER replace individual product listings with a vague paragraph summary.

LINKS FORMAT:
Whenever your answer mentions a specific community, shop, product, or Serey page, append this
block at the VERY END of your response — after all your main text:

##LINKS##
[{"label": "<display name>", "url": "<path or empty>", "type": "<community|shop|product|page>", "community_id": <id or null>}]
##END_LINKS##

Rules for the LINKS block:
- ALWAYS include it when you mention any community by name — even in general (non-discovery) answers.
- EVERY Serey page you mention by name in the reply text (e.g. Report Bug page, FAQ page, Security Disclosure Program) MUST have its own entry in the ##LINKS## block — never mention a page without giving its button. List the primary destination first.
- For communities: type = "community", community_id = real integer ID from knowledge, url = "".
- For pages: type = "page", url = the EXACT route path from knowledge (e.g. "/feed", "/blog/post/new", "/sereymarket"). NEVER leave url empty for pages.
- For shops: type = "shop", url = the shop link from knowledge (e.g. "/sereymarket?shop_id=123"). When listing multiple shops: include ONE ##LINKS## entry per shop, then add the general marketplace link last.
- For individual products: type = "product", url = the product link from knowledge (e.g. "/sereymarket/product/123"). When listing multiple products: include ONE ##LINKS## entry per product, then add the general marketplace link last.
- When listing multiple products: include ONE ##LINKS## entry per product — not just a single generic marketplace link.
- Only include entries for things you have real knowledge about — never invent IDs or paths.
- Do NOT add it for fully general answers with no specific destination.
- Do NOT add it for weather, news, or any non-Serey topic — these have no valid Serey URL to link to.
- The JSON must be a valid array — no trailing commas.
- NEVER include community IDs in the visible text — IDs belong only inside this JSON block.
- NEVER append the word "Community" to a community name. Use the exact name from the knowledge base as-is — no suffixes.
"""


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_serey_origin), Depends(_verify_api_key)])
async def chat(request: ChatRequest):
    logger.info("Model: %s | user=%s session=%s flow=%s", grok.CHAT_MODEL, request.user_id, request.session_id, request.flow or "none")
    cache_key = _cache_key(request.message, request.flow)
    session_history = get_session_history_prompt(request.session_id)

    # 1 + 2: run both ChromaDB lookups in parallel
    relevant_knowledge, long_term_memory = await asyncio.gather(
        asyncio.to_thread(search.search_serey_knowledge, request.message, 8),
        asyncio.to_thread(memory.get_user_preferences, request.user_id, request.message),
    )

    # 3. Check response cache before calling Grok (only for sessions with no prior history,
    #    so cached answers don't bleed into mid-conversation context)
    cached = _cache_get(cache_key) if not session_history else None
    if cached:
        logger.debug("Cache hit for: %s", request.message[:60])
        raw_reply = cached
    else:
        history_section = (
            f"CONVERSATION HISTORY (this session — use this to recall what the user told you):\n{session_history}"
            if session_history
            else "CONVERSATION HISTORY: (no prior turns in this session)"
        )

        page_context_section = ""
        if request.page_context and request.page_context.strip():
            page_context_section = f"""
---

CURRENT PAGE CONTENT (the text the user is writing — use this to answer their question):
{request.page_context.strip()}
"""

        flow_extra = f"\n---\n{_FLOW_PROMPTS[request.flow]}" if request.flow and request.flow in _FLOW_PROMPTS else ""
        system_prompt = SEREY_SYSTEM_PROMPT + flow_extra

        full_prompt = f"""RELEVANT KNOWLEDGE (retrieved for this question):
{relevant_knowledge}

---

USER LONG-TERM PREFERENCES (from previous sessions):
{long_term_memory}

{history_section}
{page_context_section}
---

USER: {request.message}

SEREY ASSISTANT:"""

        try:
            raw_reply = await asyncio.to_thread(grok.generate_text, full_prompt, system_prompt)
        except Exception as e:
            logger.error("Grok chat error: %s", str(e))
            raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")

        # Cache only first-turn answers (no session history) — these are the common questions
        if not session_history:
            _cache_set(cache_key, raw_reply)

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


# ---------------------------------------------------------------------------
# Background helper — runs after the streaming response is fully sent
# ---------------------------------------------------------------------------

def _persist_turn(
    session_id: str,
    user_id: str,
    user_message: str,
    assistant_reply: str,
) -> None:
    try:
        append_session_turn(
            session_id=session_id,
            user_message=user_message,
            assistant_reply=assistant_reply,
        )
    except Exception as e:
        logger.warning("Background: failed to append session turn: %s", e)
    try:
        memory.save_interaction(
            user_id=user_id,
            session_id=session_id,
            content=f"User: {user_message}\nAssistant: {assistant_reply}",
        )
    except Exception as e:
        logger.warning("Background: failed to save interaction: %s", e)


# ---------------------------------------------------------------------------
# POST /chat/stream — SSE streaming endpoint
# ---------------------------------------------------------------------------

@router.post("/chat/stream", dependencies=[Depends(require_serey_origin), Depends(_verify_api_key)])
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    logger.info("Model: %s | user=%s session=%s flow=%s", grok.CHAT_MODEL, request.user_id, request.session_id, request.flow or "none")
    """
    Streaming SSE endpoint. Emits newline-delimited events:
      data: {"type": "chunk", "text": "..."}   — progressive text tokens
      data: {"type": "links", "links": [...]}  — final structured links
      data: {"type": "done"}                   — stream complete
      data: {"type": "error", "message": "..."} — on failure
    """
    # Steps 1 + 2 run in parallel — both are independent ChromaDB queries.
    relevant_knowledge, long_term_memory = await asyncio.gather(
        asyncio.to_thread(search.search_serey_knowledge, request.message, 8),
        asyncio.to_thread(memory.get_user_preferences, request.user_id, request.message),
    )

    session_history = get_session_history_prompt(request.session_id)

    history_section = (
        f"CONVERSATION HISTORY (this session — use this to recall what the user told you):\n{session_history}"
        if session_history
        else "CONVERSATION HISTORY: (no prior turns in this session)"
    )

    page_context_section = ""
    if request.page_context and request.page_context.strip():
        page_context_section = f"""
---

CURRENT PAGE CONTENT (the text the user is writing — use this to answer their question):
{request.page_context.strip()}
"""

    flow_extra = f"\n---\n{_FLOW_PROMPTS[request.flow]}" if request.flow and request.flow in _FLOW_PROMPTS else ""
    stream_system_prompt = SEREY_SYSTEM_PROMPT + flow_extra

    full_prompt = f"""RELEVANT KNOWLEDGE (retrieved for this question):
{relevant_knowledge}

---

USER LONG-TERM PREFERENCES (from previous sessions):
{long_term_memory}

{history_section}
{page_context_section}
---

USER: {request.message}

SEREY ASSISTANT:"""

    async def event_stream():
        accumulated = ""          # rolling buffer of text NOT yet emitted
        links_marker_found = False
        final_reply = ""          # clean text to persist after stream ends

        try:
            async for chunk_text in grok.stream_text(full_prompt, stream_system_prompt):
                accumulated += chunk_text

                if not links_marker_found:
                    marker_pos = accumulated.find("##LINKS##")
                    if marker_pos == -1:
                        # Hold back last 8 chars to guard against split markers.
                        # "##LINKS##" is 9 chars, so 8-char holdback is sufficient.
                        safe_end = max(0, len(accumulated) - 8)
                        to_emit = accumulated[:safe_end]
                        if to_emit:
                            final_reply += to_emit
                            accumulated = accumulated[safe_end:]
                            yield f"data: {json.dumps({'type': 'chunk', 'text': to_emit})}\n\n"
                    else:
                        text_before = accumulated[:marker_pos]
                        if text_before:
                            final_reply += text_before
                            yield f"data: {json.dumps({'type': 'chunk', 'text': text_before})}\n\n"
                        links_marker_found = True
                        # accumulated now holds "##LINKS##..." tail; keep appending silently

        except Exception as e:
            logger.error("Grok stream error: %s", str(e))
            yield f"data: {json.dumps({'type': 'error', 'message': 'AI service error'})}\n\n"
            return

        # Flush any held-back text if no links block appeared
        if not links_marker_found:
            remaining = accumulated.strip()
            if remaining:
                final_reply += remaining
                yield f"data: {json.dumps({'type': 'chunk', 'text': remaining})}\n\n"

        # Parse ##LINKS## block from accumulated tail
        _, links = _extract_links(accumulated if links_marker_found else "")

        community_meta = get_community_metadata()
        for link in links:
            if link.type == "community" and link.community_id:
                meta = community_meta.get(link.community_id)
                if meta and meta.get("avatar"):
                    link.image = meta["avatar"]

        if links:
            yield f"data: {json.dumps({'type': 'links', 'links': [l.model_dump() for l in links]})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # Schedule persistence after the response is fully sent
        background_tasks.add_task(
            _persist_turn,
            request.session_id,
            request.user_id,
            request.message,
            final_reply,
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
