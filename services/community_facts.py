# What a community already has on Serey, for the builder: an online shop
# (the product section shows its products) and podcast episodes (the PODCAST
# section lists them). Same public endpoints the frontend builder uses:
#   GET /api/v2/sereymarket/shop/{community_id}          (LandingBuilderV2 getShop)
#   GET /api/v2/podcast/list?community_id=…&limit=1      (PodcastSection getAllPodcasts)
# Cached per community; a failed lookup returns None for that fact ("unknown")
# so the builder never adds a section on a guess.

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from scripts.serey_api_config import SEREY_MARKET_BASE

logger = logging.getLogger(__name__)

_TIMEOUT_S = 4.0
_TTL_OK_S = 600
_TTL_FAIL_S = 60
_MAX_ENTRIES = 1000
_cache: dict[int, tuple[float, dict[str, Any]]] = {}


async def _shop(client: httpx.AsyncClient, community_id: int) -> tuple[bool | None, str | None]:
    try:
        r = await client.get(f"{SEREY_MARKET_BASE}/api/v2/sereymarket/shop/{community_id}")
        r.raise_for_status()
        data = r.json()
        shops = data.get("results") if data.get("status") else []
        shops = shops if isinstance(shops, list) else []
        return bool(shops), (shops[0].get("name") if shops and isinstance(shops[0], dict) else None)
    except Exception as e:
        logger.warning("Community %s shop lookup failed: %s", community_id, e)
        return None, None


async def _podcast_episodes(client: httpx.AsyncClient, community_id: int) -> int | None:
    try:
        r = await client.get(
            f"{SEREY_MARKET_BASE}/api/v2/podcast/list",
            params={"community_id": community_id, "limit": 1, "page": 1},
        )
        r.raise_for_status()
        total = (r.json().get("pagination") or {}).get("total")
        return int(total) if total is not None else None
    except Exception as e:
        logger.warning("Community %s podcast lookup failed: %s", community_id, e)
        return None


async def get_community_facts(community_id: int | None) -> dict[str, Any]:
    """{"has_shop": bool|None, "shop_name": str|None, "podcast_episodes": int|None}."""
    unknown = {"has_shop": None, "shop_name": None, "podcast_episodes": None}
    if not community_id:
        return unknown
    cached = _cache.get(community_id)
    if cached and time.monotonic() < cached[0]:
        return cached[1]
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        (has_shop, shop_name), episodes = await asyncio.gather(
            _shop(client, community_id), _podcast_episodes(client, community_id)
        )
    facts = {"has_shop": has_shop, "shop_name": shop_name, "podcast_episodes": episodes}
    ok = has_shop is not None and episodes is not None
    if len(_cache) >= _MAX_ENTRIES:
        _cache.pop(min(_cache, key=lambda k: _cache[k][0]), None)
    _cache[community_id] = (time.monotonic() + (_TTL_OK_S if ok else _TTL_FAIL_S), facts)
    return facts
