# "This article in one minute" — 2-4 bullet TL;DR for a blog post, plus a
# reading-time estimate. Summaries are per-article, not per-reader: the first
# request pays for the AI call, everyone after reads the Redis cache.

import asyncio
import json
import logging
import os
import re
import time

import redis.asyncio as aioredis

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services import gemini_client, grok
from services.security import require_serey_origin, verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

# Articles don't change after publishing, so the summary is effectively permanent.
# Must outlive the caller's 7-day generation window by a lot: once a post is past
# that window it can never be regenerated, so an expiry here means the summary is
# gone for good.
_CACHE_TTL = 15552000  # 180 days
# Grok sees at most this much article text; enough for a TL;DR without paying
# for a 30k-character essay.
_MAX_ARTICLE_CHARS = 8000
_WORDS_PER_MINUTE = 200

# Which model writes the summary. "gemini" (default) uses gemini-3.1-flash-lite,
# the same model categorize-post runs on; set SUMMARY_PROVIDER=grok to fall back
# to grok-4.3. Cache keys are provider-agnostic, so flipping this does NOT
# invalidate summaries already cached from the other provider.
_PROVIDER = os.getenv("SUMMARY_PROVIDER", "gemini").strip().lower()

# Gemini schema: forces {"bullets": [...]} so no fence/prose stripping is needed.
_BULLETS_SCHEMA = {
    "type": "object",
    "properties": {"bullets": {"type": "array", "items": {"type": "string"}}},
    "required": ["bullets"],
}

# Fallback used ONLY when Redis is down (same rule as categorize.py: when Redis
# is up it stays the single source of truth).
_MEM_CACHE: dict[str, tuple[dict, float]] = {}

_redis: aioredis.Redis | None = None
_redis_available = True


async def _get_redis() -> aioredis.Redis | None:
    global _redis, _redis_available
    if not _redis_available:
        return None
    if _redis is None:
        try:
            url = os.getenv("REDIS_URL", "redis://localhost:6379")
            _redis = aioredis.from_url(url, decode_responses=True)
            await _redis.ping()
        except Exception as e:
            logger.warning("Redis unavailable, using in-memory summary cache: %s", e)
            _redis = None
            _redis_available = False
    return _redis


def _strip_html(html: str) -> str:
    text = _HTML_TAG_RE.sub(" ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _read_minutes(text: str) -> int:
    words = len(text.split())
    return max(1, round(words / _WORDS_PER_MINUTE))


class SummarizeRequest(BaseModel):
    author: str
    permlink: str
    article: str
    title: str = ""
    # Language to write the bullets in ("en", "km", "nl", ...). Cached per
    # language, so the same article can hold summaries in several.
    lang: str = "en"
    # False = serve from cache only, never pay for a generation. The caller
    # (serey-api) turns this off for old articles so the archive can't be walked
    # to burn Grok credits.
    allow_generate: bool = True


_SYSTEM = (
    "You summarize a blog article for readers deciding whether to read it. "
    "Return ONLY JSON: {\"bullets\": [\"...\", \"...\", \"...\"]}. "
    "Write 3 bullets (2 if the article is very short, 4 if it is long). "
    "The first bullet is the article's main point, even if it overlaps the title; "
    "the rest add facts the title does not give. Each bullet is one plain sentence "
    "under 20 words. No markdown, no numbering."
)


_LANG_NAMES = {"en": "English", "km": "Khmer", "nl": "Dutch", "zh": "Chinese",
               "es": "Spanish", "ru": "Russian", "bn": "Bengali"}

# Languages written in a non-Latin script. These must NOT get the "leave English
# terms in English" licence: given it, the model mixed Latin and even Greek letters
# into Khmer bullets ("μυshrooms"), which looks broken to a native reader.
_NON_LATIN = {"km", "zh", "ru", "bn", "ja", "ko", "ar", "th", "hi"}

# Thai and Greek are never a target script here, so a character from either inside
# a non-Latin summary is always a model glitch (observed ~1 in 6 Khmer runs: a Thai
# consonant spliced into the Khmer word for straw). Latin is excluded on purpose —
# proper nouns like "Serey" are supposed to stay in Latin letters.
_FOREIGN_SCRIPT_RE = re.compile(r"[฀-๿Ͱ-Ͽ]")


def _lang_instruction(lang: str) -> str:
    """Ask for a native-sounding summary, not a literal translation.

    A bare "write the bullets in Dutch" produced word-for-word calques of English
    sentence structure — grammatical but foreign-sounding to a native reader. Naming
    the audience and forbidding mirrored structure fixed it in testing.
    """
    name = _LANG_NAMES.get(lang, lang)
    if lang == "en":
        return "Write the bullets in English."
    instruction = (
        f"Write the bullets in {name}, the way a native {name} speaker would write them "
        f"for a {name}-speaking audience. Do not translate the English phrasing word for "
        f"word: use natural {name} word order and idiom, and re-express each idea rather "
        f"than mirroring the English sentence structure."
    )
    if lang in _NON_LATIN:
        instruction += (
            f" Write entirely in the {name} script, and never substitute a character from "
            f"another writing system (Latin, Greek, Thai) inside a {name} word. The one "
            f"exception is proper nouns and product names such as Serey: keep those in "
            f"their original Latin spelling rather than transliterating them."
        )
    else:
        instruction += (
            f" Leave terms that {name} readers normally keep in English (product names, "
            f"crypto and web jargon) in English instead of inventing a local word."
        )
    return instruction


def _parse_bullets(raw: str) -> list[str]:
    match = _JSON_RE.search(raw or "")
    if not match:
        return []
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    bullets = data.get("bullets") if isinstance(data, dict) else None
    if not isinstance(bullets, list):
        return []
    out = [str(b).strip() for b in bullets if str(b).strip()]
    return out[:4]


@router.post(
    "/summarize-post",
    dependencies=[Depends(require_serey_origin), Depends(verify_api_key)],
)
async def summarize_post(request: SummarizeRequest):
    lang = (request.lang or "en").lower()[:5]
    cache_key = f"serey:summary:{request.author}:{request.permlink}:{lang}"

    r = await _get_redis()
    if r:
        try:
            cached = await r.get(cache_key)
            if cached:
                return {**json.loads(cached), "cached": True}
        except Exception as e:
            logger.warning("Redis read failed: %s", e)
    else:
        mem = _MEM_CACHE.get(cache_key)
        if mem and (time.monotonic() - mem[1]) < _CACHE_TTL:
            return {**mem[0], "cached": True}

    article_text = await asyncio.to_thread(_strip_html, request.article)

    if not request.allow_generate:
        # Cache miss on an article we won't pay to summarize.
        return {"bullets": [], "read_minutes": _read_minutes(article_text), "lang": lang, "cached": False}

    if len(article_text.split()) < 40:
        # Too short to be worth a summary; the reader can just read it.
        return {"bullets": [], "read_minutes": _read_minutes(article_text), "lang": lang, "cached": False}

    prompt = (
        _lang_instruction(lang)
        + f"\n\nTitle: {request.title}\n\nArticle:\n{article_text[:_MAX_ARTICLE_CHARS]}"
    )

    async def _generate() -> str:
        if _PROVIDER == "grok":
            return await asyncio.to_thread(grok.generate_text, prompt, _SYSTEM, 400, grok.SUMMARY_MODEL)
        return await asyncio.to_thread(
            gemini_client.generate_json, prompt, _SYSTEM, 1200, None, _BULLETS_SCHEMA
        )

    try:
        raw = await _generate()
        bullets = _parse_bullets(raw)
        # One retry when the model splices a foreign script into a non-Latin summary.
        # It is a sampling glitch, not a prompt failure, so re-rolling usually clears it;
        # if the second try is just as broken we ship it rather than fail the request.
        if bullets and lang in _NON_LATIN and _FOREIGN_SCRIPT_RE.search(" ".join(bullets)):
            logger.warning("Foreign script in %s summary for %s/%s, retrying",
                           lang, request.author, request.permlink)
            retry = _parse_bullets(await _generate())
            if retry and not _FOREIGN_SCRIPT_RE.search(" ".join(retry)):
                bullets = retry
    except Exception as e:
        logger.error("%s summarize error: %s", _PROVIDER, e)
        raise HTTPException(status_code=502, detail="AI service unavailable")
    if not bullets:
        logger.warning("Unparseable summary for %s/%s: %.200s", request.author, request.permlink, raw)
        raise HTTPException(status_code=502, detail="Could not summarize this article")

    result = {"bullets": bullets, "read_minutes": _read_minutes(article_text), "lang": lang}

    if r:
        try:
            await r.setex(cache_key, _CACHE_TTL, json.dumps(result))
        except Exception as e:
            logger.warning("Redis write failed: %s", e)
    else:
        _MEM_CACHE[cache_key] = (result, time.monotonic())

    return {**result, "cached": False}
