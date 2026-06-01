# Serey knowledge sync service.
#
# Fetches live data from the real Serey Marketplace API in 4 chained steps:
#
#   Step 1  GET /shop-categories           → global shop categories chunk
#   Step 2  GET /shop-list?community_id=N  → shops discovered across all known communities
#   Step 3  GET /product/{community_id}    → products per shop
#   Step 4  GET /category/{community_id}   → product category tags per shop
#
# Then merges with static knowledge (serey_knowledge_catalog.py) and re-indexes ChromaDB.
#
# Triggered by:
#   - Server startup (main.py lifespan)
#   - Daily APScheduler cron at SYNC_CRON_HOUR:SYNC_CRON_MINUTE
#   - Manual POST /api/admin/sync-knowledge

import asyncio
import logging
import os
import sys

import httpx
import chromadb

logger = logging.getLogger(__name__)

_CHROMA_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chroma_db")
)
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

# Community metadata populated on every sync — used by chat.py to enrich link avatars
_community_metadata: dict[int, dict] = {}


def get_community_metadata() -> dict[int, dict]:
    """Return the latest community map: {community_id: {title, dns, avatar}}."""
    return _community_metadata


async def sync_knowledge() -> dict:
    """
    Full sync. Returns summary:
      { "indexed": int, "shops_synced": int, "products_synced": int, "errors": list[str] }
    """
    from scripts.serey_knowledge_catalog import SEREY_KNOWLEDGE, CONTEXTUAL_PREFIXES
    from scripts.serey_api_config import (
        SEREY_MARKET_BASE,
        COMMUNITY_IDS_TO_SYNC,
        PRODUCTS_PAGE_SIZE,
        transform_shop_categories,
        transform_shop_list,
        transform_single_shop,
        transform_communities,
        transform_serey_price,
        transform_content_categories,
        transform_serey_countries,
        transform_ai_training_data,
        transform_featured_items,
        transform_active_discounts,
        transform_serey_apps,
        transform_marketplace_categories,
        transform_payment_methods,
        transform_fundraising_categories,
        transform_popular_fundraisers,
        transform_country_list,
        transform_legacy_shop_categories,
        transform_subscription_plans,
    )

    errors: list[str] = []
    live_chunks: list[dict] = []
    total_products = 0

    async with httpx.AsyncClient(timeout=15.0) as client:

        # ------------------------------------------------------------------
        # Step 0 — Fetch all active communities → id→name map
        # ------------------------------------------------------------------
        community_map: dict[int, dict] = {}
        try:
            r = await client.get(f"{SEREY_MARKET_BASE}/api/v2/community/categories/list")
            r.raise_for_status()
            comm_chunk, community_map = transform_communities(r.json())
            live_chunks.append({
                "id": "live_communities",
                "category": "platform",
                **comm_chunk,
            })
            _community_metadata.clear()
            _community_metadata.update(community_map)
            logger.info("Step 0: fetched %d active communities.", len(community_map))
        except Exception as e:
            errors.append(f"community-list: {e}")
            logger.warning("Step 0 failed, falling back to hardcoded IDs: %s", e)
            community_map = {cid: {"title": f"Community {cid}", "dns": None} for cid in COMMUNITY_IDS_TO_SYNC}

        # ------------------------------------------------------------------
        # Step 1 — Global shop categories
        # ------------------------------------------------------------------
        try:
            r = await client.get(f"{SEREY_MARKET_BASE}/api/v2/sereymarket/shop-categories")
            r.raise_for_status()
            results = r.json().get("results", [])
            transformed = transform_shop_categories(results)
            live_chunks.append({
                "id": "live_shop_categories",
                "category": "marketplace",
                **transformed,
            })
            logger.info("Step 1: fetched %d shop categories.", len(results))
        except Exception as e:
            errors.append(f"shop-categories: {e}")
            logger.warning("Step 1 failed: %s", e)

        # ------------------------------------------------------------------
        # Step 2 — Discover all shops across all known community IDs
        # ------------------------------------------------------------------
        all_shops: dict[int, dict] = {}  # keyed by shop_id to deduplicate

        for community_id, community_info in community_map.items():
            community_name = community_info["title"]
            try:
                r = await client.get(
                    f"{SEREY_MARKET_BASE}/api/v2/sereymarket/shop-list",
                    params={"community_id": community_id},
                )
                r.raise_for_status()
                shops = r.json().get("results", [])
                for s in shops:
                    sid = s.get("id")
                    if sid and sid not in all_shops:
                        s["_community_name"] = community_map[community_id]["title"]
                        s["_community_dns"] = community_map[community_id]["dns"] or ""
                        all_shops[sid] = s
            except Exception as e:
                errors.append(f"shop-list community {community_id} ({community_name}): {e}")
                logger.warning("Step 2 community %d (%s) failed: %s", community_id, community_name, e)

        unique_shops = list(all_shops.values())
        logger.info("Step 2: discovered %d unique shops.", len(unique_shops))

        if unique_shops:
            transformed = transform_shop_list(unique_shops)
            live_chunks.append({
                "id": "live_shops_overview",
                "category": "shops",
                **transformed,
            })

        # ------------------------------------------------------------------
        # Step 3 & 4 — Per-shop: products + product categories
        # ------------------------------------------------------------------
        for shop in unique_shops:
            shop_id = shop.get("id")
            shop_community_id = shop.get("community_id")
            shop_name = shop.get("name", f"shop_{shop_id}")

            if not shop_id or not shop_community_id:
                continue

            products: list[dict] = []
            categories: list[dict] = []

            # Step 3: products
            try:
                r = await client.get(
                    f"{SEREY_MARKET_BASE}/api/v2/sereymarket/product/{shop_community_id}",
                    params={"page": 1, "pageSize": PRODUCTS_PAGE_SIZE, "shop_id": shop_id},
                )
                r.raise_for_status()
                products = r.json().get("data", {}).get("products", [])
                total_products += len(products)
            except Exception as e:
                errors.append(f"products shop {shop_id}: {e}")
                logger.warning("Step 3 shop %d products failed: %s", shop_id, e)

            # Step 3b: books (serey stores books in a completely separate subsystem)
            try:
                r = await client.get(
                    f"{SEREY_MARKET_BASE}/api/v2/book-information/books",
                    params={"shop_id": shop_id, "page": 1, "pageSize": PRODUCTS_PAGE_SIZE},
                )
                if r.status_code == 200:
                    books = r.json().get("data", {}).get("books", [])
                    if books:
                        # Append books into the products array so the transform step handles them together
                        products.extend(books)
                        total_products += len(books)
            except Exception as e:
                errors.append(f"books shop {shop_id}: {e}")
                logger.warning("Step 3b shop %d books failed: %s", shop_id, e)

            # Step 4: product categories
            try:
                r = await client.get(
                    f"{SEREY_MARKET_BASE}/api/v2/sereymarket/category/{shop_community_id}",
                    params={"shop_id": shop_id},
                )
                r.raise_for_status()
                categories = r.json().get("data", [])
            except Exception as e:
                errors.append(f"categories shop {shop_id}: {e}")
                logger.warning("Step 4 shop %d categories failed: %s", shop_id, e)

            community_info = community_map.get(shop_community_id) or {}
            community_name = community_info.get("title") or shop.get("_community_name", "")
            community_dns = community_info.get("dns") or shop.get("_community_dns", "")
            if community_name:
                shop["_community_name"] = community_name
            if community_dns:
                shop["_community_dns"] = community_dns
            transformed = transform_single_shop(shop, products, categories)
            live_chunks.append({
                "id": f"live_shop_{shop_id}",
                "category": "shops",
                **transformed,
            })

        # ------------------------------------------------------------------
        # Step 5 — General platform data (price, categories, countries, AI data)
        # ------------------------------------------------------------------

        # 5a. SEREY token price + supported token prices
        try:
            price_r, tokens_r = await asyncio.gather(
                client.get(f"{SEREY_MARKET_BASE}/api/v2/general/serey-price"),
                client.get(f"{SEREY_MARKET_BASE}/api/v2/general/supported-token-prices"),
                return_exceptions=True,
            )
            price_data = price_r.json() if not isinstance(price_r, Exception) else {}
            token_data = tokens_r.json() if not isinstance(tokens_r, Exception) else {}
            live_chunks.append({
                "id": "live_serey_price",
                "category": "platform",
                **transform_serey_price(price_data, token_data),
            })
            logger.info("Step 5a: fetched SEREY price.")
        except Exception as e:
            errors.append(f"serey-price: {e}")
            logger.warning("Step 5a failed: %s", e)

        # 5b. Content post categories
        try:
            r = await client.get(f"{SEREY_MARKET_BASE}/api/v2/general/list-serey-web-categories")
            r.raise_for_status()
            live_chunks.append({
                "id": "live_content_categories",
                "category": "platform",
                **transform_content_categories(r.json()),
            })
            logger.info("Step 5b: fetched content categories.")
        except Exception as e:
            errors.append(f"content-categories: {e}")
            logger.warning("Step 5b failed: %s", e)

        # 5c. Supported countries
        try:
            r = await client.get(f"{SEREY_MARKET_BASE}/api/v2/general/serey-countries")
            r.raise_for_status()
            live_chunks.append({
                "id": "live_serey_countries",
                "category": "platform",
                **transform_serey_countries(r.json()),
            })
            logger.info("Step 5c: fetched supported countries.")
        except Exception as e:
            errors.append(f"serey-countries: {e}")
            logger.warning("Step 5c failed: %s", e)

        # 5d. Marketplace AI training data (products + shops + FAQs + featured items + discounts)
        try:
            r = await client.get(
                f"{SEREY_MARKET_BASE}/api/v2/sereymarket/ai-training-data",
                params={"page": 1, "pageSize": 50},
            )
            r.raise_for_status()
            ai_data = r.json()
            live_chunks.append({
                "id": "live_ai_training_data",
                "category": "marketplace",
                **transform_ai_training_data(ai_data),
            })
            live_chunks.append({
                "id": "live_featured_items",
                "category": "marketplace",
                **transform_featured_items(ai_data),
            })
            live_chunks.append({
                "id": "live_active_discounts",
                "category": "marketplace",
                **transform_active_discounts(ai_data),
            })
            logger.info("Step 5d: fetched AI training data (incl. featured items + active discounts).")
        except Exception as e:
            errors.append(f"ai-training-data: {e}")
            logger.warning("Step 5d failed: %s", e)

        # ------------------------------------------------------------------
        # Step 6 — Additional public endpoints (parallel fetch)
        # ------------------------------------------------------------------
        # (chunk_id, category, path, transform_fn, params)
        step6_endpoints = [
            ("live_serey_apps",             "platform",    "/api/v2/general/list-app",                              transform_serey_apps,              {}),
            ("live_marketplace_categories", "marketplace", "/api/v2/general/list-marketplace-categories",           transform_marketplace_categories,  {}),
            ("live_payment_methods",        "marketplace", "/api/v2/sereymarket/payment",                           transform_payment_methods,         {}),
            ("live_fundraising_categories", "community",   "/api/v2/fundraising/get-categories",                    transform_fundraising_categories,  {}),
            ("live_popular_fundraisers",    "community",   "/api/v2/fundraising/get-popular-pagination",            transform_popular_fundraisers,     {"page": 1, "pageSize": 20}),
            ("live_country_list",           "platform",    "/api/v2/country/list-countries",                        transform_country_list,            {}),
            ("live_legacy_shop_categories", "marketplace", "/api/v2/marketplace/list-online-shop-categories",       transform_legacy_shop_categories,  {}),
            ("live_subscription_plans",     "platform",    "/api/v2/subscription/list-all-subscriptions",           transform_subscription_plans,      {}),
        ]

        step6_reqs = await asyncio.gather(
            *[client.get(f"{SEREY_MARKET_BASE}{path}", params=params) for _, _, path, _, params in step6_endpoints],
            return_exceptions=True,
        )

        for (chunk_id, category, path, transform_fn, _), result in zip(step6_endpoints, step6_reqs):
            if isinstance(result, Exception):
                errors.append(f"{chunk_id}: {result}")
                logger.warning("Step 6 %s failed: %s", chunk_id, result)
                continue
            try:
                result.raise_for_status()
                live_chunks.append({
                    "id": chunk_id,
                    "category": category,
                    **transform_fn(result.json()),
                })
            except Exception as e:
                errors.append(f"{chunk_id}: {e}")
                logger.warning("Step 6 %s transform failed: %s", chunk_id, e)

        logger.info("Step 6: fetched %d additional platform chunks.", len(step6_reqs))

        # ------------------------------------------------------------------
        # Step 7 — Cambodia weather (Open-Meteo, no API key required)
        # ------------------------------------------------------------------
        try:
            weather_r = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": 11.5625,
                    "longitude": 104.916,
                    "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
                    "timezone": "Asia/Phnom_Penh",
                    "forecast_days": 3,
                },
            )
            weather_r.raise_for_status()
            w = weather_r.json()
            current = w.get("current", {})
            daily = w.get("daily", {})

            WMO_DESCRIPTIONS = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Foggy", 48: "Depositing rime fog",
                51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
                95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
            }

            def wmo(code):
                return WMO_DESCRIPTIONS.get(code, f"Code {code}")

            dates = daily.get("time", [])
            forecast_lines = []
            for i, date in enumerate(dates):
                forecast_lines.append(
                    f"  {date}: {wmo(daily['weather_code'][i])}, "
                    f"high {daily['temperature_2m_max'][i]}°C / low {daily['temperature_2m_min'][i]}°C, "
                    f"rain {daily['precipitation_sum'][i]}mm"
                )

            content = (
                f"Current conditions in Phnom Penh, Cambodia:\n"
                f"  Temperature: {current.get('temperature_2m')}°C\n"
                f"  Humidity: {current.get('relative_humidity_2m')}%\n"
                f"  Precipitation: {current.get('precipitation')}mm\n"
                f"  Wind speed: {current.get('wind_speed_10m')} km/h\n"
                f"  Conditions: {wmo(current.get('weather_code', -1))}\n\n"
                f"3-day forecast:\n" + "\n".join(forecast_lines)
            )

            live_chunks.append({
                "id": "live_cambodia_weather",
                "category": "general",
                "title": f"Cambodia Weather — {current.get('time', 'today')[:10]}",
                "content": content,
            })
            logger.info("Step 7: fetched Cambodia weather.")
        except Exception as e:
            errors.append(f"cambodia-weather: {e}")
            logger.warning("Step 7 weather fetch failed: %s", e)

    logger.info(
        "Final sync: %d shops, %d products, %d total live chunks, %d errors.",
        len(unique_shops), total_products, len(live_chunks), len(errors),
    )

    # ------------------------------------------------------------------
    # Merge: static base knowledge + live chunks (live overrides by id)
    # ------------------------------------------------------------------
    merged: dict[str, dict] = {}

    # Load static first
    for entry in SEREY_KNOWLEDGE:
        merged[entry["id"]] = {
            "id": entry["id"],
            "category": entry["category"],
            "title": entry["title"],
            "content": entry["content"],
        }

    # Live chunks override/add on top
    for chunk in live_chunks:
        merged[chunk["id"]] = chunk

    # ------------------------------------------------------------------
    # Build the document/metadata/id lists (no DB interaction yet)
    # ------------------------------------------------------------------
    documents, metadatas, ids = [], [], []
    for chunk in merged.values():
        # Apply contextual prefix for embedding if defined — improves retrieval for long chunks.
        # The prefix is NOT stored in metadata, so prompts always receive clean original content.
        prefix = CONTEXTUAL_PREFIXES.get(chunk["id"], "")
        doc_text = (
            f"{prefix}\n\n{chunk['title']}\n\n{chunk['content']}"
            if prefix
            else f"{chunk['title']}\n\n{chunk['content']}"
        )
        documents.append(doc_text)
        metadatas.append({
            "id": chunk["id"],
            "category": chunk["category"],
            "title": chunk["title"],
            "content": chunk["content"],
        })
        ids.append(chunk["id"])

    # ------------------------------------------------------------------
    # Re-index ChromaDB. The delete→create→add sequence can intermittently
    # raise "Collection [uuid] does not exist" due to a stale client cache,
    # which would otherwise wipe the KB without repopulating it. Retry with a
    # fresh client to guarantee the collection is left populated.
    # ------------------------------------------------------------------
    total_indexed = 0
    last_err: Exception | None = None
    for attempt in range(1, 4):
        client_db = chromadb.PersistentClient(path=_CHROMA_PATH)
        try:
            try:
                client_db.delete_collection("serey_knowledge")
            except Exception:
                pass
            collection = client_db.create_collection(
                name="serey_knowledge",
                metadata={"hnsw:space": "cosine"},
            )
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            total_indexed = collection.count()
            break
        except Exception as e:
            last_err = e
            logger.warning("Re-index attempt %d failed: %s", attempt, e)
    else:
        # All attempts failed — surface the error rather than returning a wiped KB silently.
        raise RuntimeError(f"Failed to re-index serey_knowledge after 3 attempts: {last_err}")

    summary = {
        "indexed": total_indexed,
        "shops_synced": len(unique_shops),
        "products_synced": total_products,
        "errors": errors,
    }
    logger.info("Knowledge sync complete: %s", summary)
    return summary
