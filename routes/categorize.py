import asyncio
import json
import logging
import os
import re
import time

import redis.asyncio as aioredis

from google import genai
from google.genai import types
import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

_gemini_client = None

def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        _gemini_client = genai.Client(api_key=key)
    return _gemini_client

router = APIRouter()
logger = logging.getLogger(__name__)

_SEREY_API_BASE = "https://global-api.serey.io"
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# In-memory fallback cache: community_name → (categories, fetched_at)
_CAT_CACHE: dict[str, tuple[list[dict], float]] = {}
_CAT_CACHE_TTL = 2592000  # 30 days — Node.js invalidates serey:categories:* on any category mutation

_redis: aioredis.Redis | None = None
_redis_available = True  # flipped to False on first connection failure


async def _get_redis() -> aioredis.Redis | None:
    global _redis, _redis_available
    if not _redis_available:
        return None
    if _redis is None:
        try:
            url = os.getenv("REDIS_URL", "redis://localhost:6379")
            _redis = aioredis.from_url(url, decode_responses=True)
            await _redis.ping()
            logger.info("Redis connected: %s", url)
        except Exception as e:
            logger.warning("Redis unavailable, falling back to in-memory cache: %s", e)
            _redis = None
            _redis_available = False
    return _redis


def _strip_html(html: str) -> str:
    text = _HTML_TAG_RE.sub(" ", html)
    return re.sub(r"\s+", " ", text).strip()


class CategorizeRequest(BaseModel):
    community_id: int
    community_name: str
    article: str


async def _fetch_categories(community_name: str, token: str) -> list[dict]:
    redis_key = f"serey:categories:{community_name}"

    # 1. Try Redis
    r = await _get_redis()
    if r:
        try:
            cached = await r.get(redis_key)
            if cached:
                logger.info("Redis cache hit for community=%s", community_name)
                return json.loads(cached)
        except Exception as e:
            logger.warning("Redis read failed: %s", e)

    # 2. Try in-memory fallback
    mem = _CAT_CACHE.get(community_name)
    if mem and (time.monotonic() - mem[1]) < _CAT_CACHE_TTL:
        logger.info("In-memory cache hit for community=%s", community_name)
        return mem[0]

    # 3. Fetch from Serey API
    url = f"{_SEREY_API_BASE}/api/v2/category/list-by-community"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, params={"community": community_name}, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Categories raw response for %s: %s", community_name, str(data)[:300])
            items = data.get("categories") or (data if isinstance(data, list) else [])
            categories = [
                c for c in items
                if isinstance(c, dict) and c.get("id") and c.get("name") and not c.get("deleted")
            ]
            logger.info("Fetched %d categories for community=%s", len(categories), community_name)

            # Store in Redis (TTL 5 min)
            if r and categories:
                try:
                    await r.setex(redis_key, _CAT_CACHE_TTL, json.dumps(categories))
                except Exception as e:
                    logger.warning("Redis write failed: %s", e)

            # Always update in-memory too
            _CAT_CACHE[community_name] = (categories, time.monotonic())
            return categories
        except Exception as e:
            logger.warning("Failed to fetch categories from Serey API: %s", e)
            return []


_SYSTEM = 'Classify the article. Return only JSON with main_category_id (int), sub_category_name (string from that category\'s sub_categories list or null), and parent_category_id (int or null). IDs must be from the list.'


def _build_prompt(article_text: str, categories: list[dict]) -> str:
    lines = []
    for c in categories[:40]:
        subs = [s["name"] for s in c.get("sub_categories") or [] if s.get("name")]
        sub_str = f" (sub: {', '.join(subs)})" if subs else ""
        lines.append(f"{c['id']}:{c['name']}{sub_str}")
    return f"Categories:\n" + "\n".join(lines) + f"\n\nArticle:\n{article_text[:300]}"


def _pick_category(categories: list[dict], cat_id) -> dict | None:
    if cat_id is None:
        return None
    try:
        target = int(cat_id)
    except (TypeError, ValueError):
        return None
    return next((c for c in categories if c.get("id") == target), None)


@router.post("/categorize-post")
async def categorize_post(
    request: CategorizeRequest,
    authorization: str = Header(default=""),
):
    token = authorization[7:].strip() if authorization.startswith("Bearer ") else ""

    # Run HTML stripping and category fetch in parallel
    article_text, categories = await asyncio.gather(
        asyncio.to_thread(_strip_html, request.article),
        _fetch_categories(request.community_name, token),
    )

    if not article_text:
        logger.warning("Empty article text after HTML strip")
        return {}

    if not categories:
        logger.warning("No categories available — community=%s", request.community_name)
        return {}

    prompt = _SYSTEM + "\n\n" + _build_prompt(article_text, categories)
    try:
        client = _get_gemini()
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "main_category_id": {"type": "integer"},
                        "sub_category_name": {"type": "string", "nullable": True},
                        "parent_category_id": {"type": "integer", "nullable": True},
                    },
                    "required": ["main_category_id", "sub_category_name", "parent_category_id"],
                },
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=150,
                temperature=0.1,
            ),
        )
        # Extract text from the non-thinking part only
        raw = next(
            (p.text for p in response.candidates[0].content.parts if not getattr(p, "thought", False)),
            response.text or "",
        )
    except Exception as e:
        logger.error("Gemini categorize error: %s", e)
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")

    logger.info("Gemini raw response: %s", raw[:200])

    try:
        json_match = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
        result = json.loads(json_match.group()) if json_match else {}
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning("AI returned unparseable JSON (%s): %.200s", e, raw)
        return {}

    main_cat = _pick_category(categories, result.get("main_category_id"))
    parent_cat = _pick_category(categories, result.get("parent_category_id"))

    if not main_cat:
        logger.warning("AI picked no valid main_category — result=%s", result)
        return {}

    # Look up sub_category by name from the matched category's sub_categories list
    sub_cat_obj = None
    sub_name = result.get("sub_category_name")
    if sub_name:
        sub_cat_obj = next(
            (s for s in (main_cat.get("sub_categories") or []) if s.get("name") == sub_name),
            None,
        )

    if parent_cat and parent_cat["id"] == main_cat["id"]:
        parent_cat = None

    community_categories: list = [{"categories": [main_cat]}]
    if sub_cat_obj:
        community_categories.append(sub_cat_obj)

    return {
        "community_categories": community_categories,
        "parent_categories": [parent_cat] if parent_cat else [],
    }
