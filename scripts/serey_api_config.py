# Real Serey Marketplace API configuration.
# Base: https://global-api.serey.io
#
# Sync strategy (executed in order by knowledge_sync.py):
#
#   Step 1 — Global shop categories
#             GET /api/v2/sereymarket/shop-categories
#             → 1 knowledge chunk "Shop Categories"
#
#   Step 2 — Shop list per community
#             GET /api/v2/sereymarket/shop-list?community_id={id}
#             for each id in COMMUNITY_IDS_TO_SYNC
#             → shops are deduplicated by shop_id, then 1 summary chunk + per-shop chunks
#
#   Step 3 — Products per shop
#             GET /api/v2/sereymarket/product/{community_id}?shop_id={shop_id}&page=1&pageSize=N
#             → 1 knowledge chunk per shop listing its products
#
#   Step 4 — Shop categories per shop (product category tags)
#             GET /api/v2/sereymarket/category/{community_id}?shop_id={shop_id}
#             → merged into the per-shop chunk
#
# Community IDs are now fetched LIVE from:
#   GET /api/v2/community/categories/list  → "communities"[*].communities[]
# COMMUNITY_IDS_TO_SYNC below is only used as a fallback if that endpoint fails.

# ---------------------------------------------------------------------------
# Real API base URL
# ---------------------------------------------------------------------------
SEREY_MARKET_BASE = "https://global-api.serey.io"

# Public Serey website base (frontend URLs for user-facing links)
SEREY_SITE_URL = "https://serey.io"

# ---------------------------------------------------------------------------
# Community IDs to crawl.
# Each community can have its own shops. Add new community IDs here as they
# are created on the Serey platform.
# IDs discovered from the live shop-list API (March 2026):
# ---------------------------------------------------------------------------
COMMUNITY_IDS_TO_SYNC = [3, 57, 60, 63, 65, 66, 69, 70, 108]

# Max products fetched per shop per sync
PRODUCTS_PAGE_SIZE = 100


# ---------------------------------------------------------------------------
# Transform helpers — map real API response shapes → {title, content} chunks
# ---------------------------------------------------------------------------

def transform_shop_categories(results: list) -> dict:
    """
    Endpoint: GET /api/v2/sereymarket/shop-categories
    Response key: "results"  (list of {id, name, description, color})
    """
    lines = [
        f"{c['name']} — {c.get('description', '')}"
        for c in results
        if not c.get("deleted")
    ]
    return {
        "title": "Serey Marketplace Shop Categories",
        "content": (
            "Serey organises shops into the following categories: "
            + "; ".join(lines) + ". "
            "Buyers can filter shops by these categories on the marketplace."
        ),
    }


def transform_shop_list(shops: list) -> dict:
    """
    Endpoint: GET /api/v2/sereymarket/shop-list?community_id={id}
    Response key: "results"  (list of shop objects)
    Builds an overview chunk listing all discovered shops.
    """
    lines = []
    for s in shops:
        name = s.get("name", "")
        desc = s.get("description") or ""
        hours = "24 hours" if s.get("is_24_hours") else (
            f"{s.get('opening_hour', '')}–{s.get('closing_hour', '')}"
        )
        lines.append(f"{name}: {desc} (open {hours})")
    return {
        "title": "Shops Available on Serey Marketplace",
        "content": (
            f"There are currently {len(shops)} shops on Serey: "
            + "; ".join(lines) + "."
        ),
    }


def transform_single_shop(shop: dict, products: list, categories: list) -> dict:
    """
    Combines shop detail + products + categories into one rich knowledge chunk per shop.
    Called once per shop during the sync.
    """
    name = shop.get("name", "")
    desc = shop.get("description") or "No description."
    hours = "open 24 hours" if shop.get("is_24_hours") else (
        f"open {shop.get('opening_hour', 'unknown')}–{shop.get('closing_hour', 'unknown')}"
    )
    is_open = "currently open" if not shop.get("is_closed") else "currently closed"

    # Category names this shop uses for its products
    cat_names = [c.get("name", "") for c in categories if not c.get("deleted")]

    # Product and Book lines
    product_lines = []
    for p in products:
        # Check if it's a book (from the /book-information/books endpoint)
        if "book_title" in p:
            b_title = p.get("book_title", "")
            b_author = p.get("author", "Unknown Author")
            b_price = p.get("price", "0")
            b_qty = p.get("quantity", 0)
            product_lines.append(
                f'Book: "{b_title}" by {b_author} (price: ${float(b_price):.2f}, qty: {b_qty})'
            )
        else:
            # Standard product
            p_name = p.get("name", "")
            p_price = p.get("price", "0")
            p_coin = p.get("price_serey_coin", "0")
            p_cat = p.get("category_name", "")
            p_qty = p.get("quantity", 0)
            product_lines.append(
                f"{p_name} (category: {p_cat}, price: ${float(p_price):.2f} / {float(p_coin):.0f} SEREY coins, qty: {p_qty})"
            )

    community_name = shop.get("_community_name", "")
    community_label = f" in the {community_name} community" if community_name else ""
    shop_id = shop.get("id", "")
    community_id = shop.get("community_id", "")
    community_dns = shop.get("_community_dns", "")  # e.g. "bookclub.serey.io"
    shop_url = (
        f"https://{community_dns}/sereymarket?shop_id={shop_id}"
        if shop_id and community_dns else ""
    )

    content_parts = [
        f"{name} is a shop on Serey Marketplace{community_label}. {desc}",
        f"Status: {is_open}, {hours}.",
    ]
    if shop_url:
        content_parts.append(f"Shop URL: {shop_url}")
    if cat_names:
        content_parts.append(f"Product categories in this shop: {', '.join(cat_names)}.")
    if product_lines:
        # Embed product-level URLs using community subdomain
        prod_url_lines = []
        for p in products:
            p_id = p.get("id", "")
            p_shop_id = p.get("shop_id", "") or shop_id
            
            # Identify if it's a book or standard product
            if "book_title" in p:
                p_name = p.get("book_title", "")
                p_type = "book"
            else:
                p_name = p.get("name", "")
                p_type = "product"

            if p_id and p_name and community_dns:
                prod_url_lines.append(
                    f"{p_name}: https://{community_dns}/sereymarket/product/{p_id}?shop_id={p_shop_id}&type={p_type}"
                )
        content_parts.append(
            f"Products available: " + "; ".join(product_lines) + "."
        )
        if prod_url_lines:
            content_parts.append("Product URLs: " + "; ".join(prod_url_lines) + ".")
    else:
        content_parts.append("This shop currently has no listed products.")

    return {
        "title": f"Shop: {name}",
        "content": " ".join(content_parts),
    }


def transform_communities(data: dict) -> tuple[dict, dict]:
    """
    Endpoint: GET /api/v2/community/categories/list
    Response key: "communities" (list of { category_name, communities[] })

    Returns:
      (chunk dict, community_map {id: {"title": str, "dns": str|None}})
      Only includes published, non-deleted communities.
    """
    community_map: dict[int, dict] = {}
    category_lines: list[str] = []

    for cat in data.get("communities", []):
        cat_name = cat.get("category_name", "")
        members: list[str] = []
        for c in cat.get("communities", []):
            if not c.get("deleted") and c.get("is_publish"):
                cid = c.get("id")
                title = c.get("title", "")
                dns = c.get("dns") or None
                if cid:
                    community_map[cid] = {"title": title, "dns": dns}
                    members.append(f"{title} (id: {cid})")
        if members:
            category_lines.append(f"{cat_name}: {', '.join(members)}")

    chunk = {
        "title": "Serey Communities",
        "content": (
            f"Serey has {len(community_map)} active communities organized into categories. "
            + " | ".join(category_lines) + "."
        ),
    }
    return chunk, community_map


def transform_serey_price(price_data: dict, token_data: dict) -> dict:
    """
    Endpoints:
      GET /api/v2/general/serey-price             → { price, ... }
      GET /api/v2/general/supported-token-prices  → { data: [{symbol, price, ...}] }
    """
    serey_price = price_data.get("price") or price_data.get("data", {}).get("price", "N/A")
    token_lines = []
    for t in (token_data.get("data") or []):
        symbol = t.get("symbol", "")
        p = t.get("price", "")
        if symbol:
            token_lines.append(f"{symbol}: ${p}")
    return {
        "title": "SEREY Token Price and Supported Tokens",
        "content": (
            f"The current SEREY token price is ${serey_price}. "
            + ("Supported token prices: " + ", ".join(token_lines) + "." if token_lines else "")
        ),
    }


def transform_content_categories(data) -> dict:
    """
    Endpoint: GET /api/v2/general/list-serey-web-categories
    Response: list or { data: [...] } of category objects {id, name, ...}
    """
    items = data if isinstance(data, list) else (data.get("data") or data.get("categories") or [])
    names = [c.get("name", "") for c in items if not c.get("deleted") and c.get("name")]
    return {
        "title": "Serey Content Categories",
        "content": (
            "Serey posts are organized into the following categories: "
            + ", ".join(names) + ". "
            "Users can filter and browse content by these categories."
        ),
    }


def transform_serey_countries(data) -> dict:
    """
    Endpoint: GET /api/v2/general/serey-countries
    Real response: { countries: [{country_name, icon_url, ...}] }
    """
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = (
            data.get("countries")
            or data.get("data")
            or []
        )
    else:
        items = []
    names = [
        c.get("country_name") or c.get("name") or c.get("country", "")
        for c in items
        if c.get("country_name") or c.get("name") or c.get("country")
    ]
    return {
        "title": "Countries Supported by Serey",
        "content": (
            f"Serey supports communities from {len(names)} countries: "
            + ", ".join(names) + "."
        ),
    }


def transform_ai_training_data(data: dict) -> dict:
    """
    Endpoint: GET /api/v2/sereymarket/ai-training-data?page=1&pageSize=50
    Real response shape:
      data.products_and_services.{categories[], products[], total_products}
      data.shops.{shops[], total_shops}
      data.faqs.{general[], shop_owners[]}
      data.operation_guidelines.{order_processing, shop_operations, product_management}
    """
    if not isinstance(data, dict):
        return {"title": "Serey Marketplace AI Training Data", "content": "No AI training data available."}
    inner = data.get("data") or {}
    if not isinstance(inner, dict):
        inner = {}

    pas = inner.get("products_and_services") or {}
    products = pas.get("products") or [] if isinstance(pas, dict) else []
    shops_block = inner.get("shops") or {}
    shops = shops_block.get("shops") or [] if isinstance(shops_block, dict) else []
    faqs_block = inner.get("faqs") or {}
    faqs_general = faqs_block.get("general") or [] if isinstance(faqs_block, dict) else []
    faqs_owners = faqs_block.get("shop_owners") or [] if isinstance(faqs_block, dict) else []
    guidelines = inner.get("operation_guidelines") or {}

    parts = []

    if shops:
        shop_names = [s.get("name") or s.get("shop_name", "") for s in shops if s.get("name") or s.get("shop_name")]
        parts.append(f"Active shops on Serey Marketplace: {', '.join(shop_names[:30])}.")

    if products:
        prod_lines = []
        for p in products[:30]:
            n = p.get("name", "")
            price = p.get("price", "")
            shop = p.get("shop_name", "")
            prod_lines.append(f"{n} (shop: {shop}, price: ${price})" if shop else f"{n} (${price})")
        parts.append(f"Sample products: {'; '.join(prod_lines)}.")

    all_faqs = faqs_general + faqs_owners
    if all_faqs:
        faq_lines = [
            f"Q: {f.get('question', '')} A: {f.get('answer', '')}"
            for f in all_faqs[:10]
            if f.get("question")
        ]
        if faq_lines:
            parts.append("FAQs: " + " | ".join(faq_lines) + ".")

    if isinstance(guidelines, dict):
        for key, val in guidelines.items():
            if isinstance(val, str) and val:
                parts.append(f"{key.replace('_', ' ').title()}: {val[:200]}")

    return {
        "title": "Serey Marketplace AI Training Data",
        "content": " ".join(parts) if parts else "No AI training data available.",
    }


# ---------------------------------------------------------------------------
# Step 6 transforms — additional public endpoints
# ---------------------------------------------------------------------------

def transform_featured_items(data: dict) -> dict:
    """
    Endpoint: GET /api/v2/sereymarket/ai-training-data  (key: "featured_items")
    Shape:
      featured_items.by_community[]: { community_id, items[]: {
        position, item_type ("product"|"book"), id, title, price,
        shop_id (null for books), discount_percentage, discount_expires_at (null = no expiry),
        images[] } }
      featured_items.total_communities: int
    Field may live at top level or nested under "data".
    """
    inner = data.get("data") if isinstance(data, dict) else {}
    if not isinstance(inner, dict):
        inner = {}
    featured = data.get("featured_items") or inner.get("featured_items") or {}
    by_community = featured.get("by_community") or []
    total = featured.get("total_communities", len(by_community))

    lines = []
    for comm in by_community:
        cid = comm.get("community_id", "")
        items = comm.get("items") or []
        item_parts = []
        for it in items:
            title = it.get("title", "")
            price = it.get("price", "")
            itype = it.get("item_type", "item")
            item_id = it.get("id", "")
            shop_id = it.get("shop_id")
            disc = it.get("discount_percentage")
            expires = it.get("discount_expires_at")  # null means no expiry
            disc_str = ""
            if disc:
                disc_str = f", {disc}% off"
                if expires:
                    disc_str += f" (expires {expires})"
                else:
                    disc_str += " (permanent discount)"
            if item_id:
                if itype == "book":
                    url = f"/sereymarket/product/{item_id}?type=book"
                elif shop_id:
                    url = f"/sereymarket/product/{item_id}?shop_id={shop_id}"
                else:
                    url = f"/sereymarket/product/{item_id}"
                item_parts.append(f"[{title}]({url}) ({itype}, ${price}{disc_str})")
            else:
                item_parts.append(f"{title} ({itype}, ${price}{disc_str})")
        if item_parts:
            lines.append(f"Community {cid}: {'; '.join(item_parts)}")

    return {
        "title": "Serey Marketplace Featured Items",
        "content": (
            f"Serey Marketplace features highlighted items across {total} communities. "
            + " | ".join(lines) + "."
            if lines else "No featured items currently available."
        ),
    }


def transform_active_discounts(data: dict) -> dict:
    """
    Endpoint: GET /api/v2/sereymarket/ai-training-data  (key: "active_discounts")
    Shape:
      active_discounts.items[]: { item_type ("product"|"book"), id, title, price,
        discounted_price (pre-calculated), shop_id, discount_percentage,
        discount_expires_at (null = permanent), images[] }
      active_discounts.total: int
    Items are pre-sorted by discount_expires_at ascending (soonest expiring first).
    Items with discount_expires_at: null are permanently discounted until manually removed.
    Field may live at top level or nested under "data".
    """
    inner = data.get("data") if isinstance(data, dict) else {}
    if not isinstance(inner, dict):
        inner = {}
    discounts = data.get("active_discounts") or inner.get("active_discounts") or {}
    items = discounts.get("items") or []
    total = discounts.get("total", len(items))

    lines = []
    for it in items:
        title = it.get("title", "")
        original = it.get("price", "")
        discounted = it.get("discounted_price", "")
        pct = it.get("discount_percentage", "")
        expires = it.get("discount_expires_at")  # null = permanent
        itype = it.get("item_type", "item")
        item_id = it.get("id", "")
        shop_id = it.get("shop_id")
        if item_id:
            if itype == "book":
                url = f"/sereymarket/product/{item_id}?type=book"
            elif shop_id:
                url = f"/sereymarket/product/{item_id}?shop_id={shop_id}"
            else:
                url = f"/sereymarket/product/{item_id}"
            line = f"[{title}]({url}) ({itype}): was ${original}, now ${discounted} ({pct}% off)"
        else:
            line = f"{title} ({itype}): was ${original}, now ${discounted} ({pct}% off)"
        if expires:
            line += f", expires {expires}"
        else:
            line += ", no expiry date (permanent)"
        lines.append(line)

    return {
        "title": "Serey Marketplace Active Discounts",
        "content": (
            f"There are currently {total} active discounts on Serey Marketplace, listed soonest-expiring first. "
            + " | ".join(lines) + ". "
            "Note: items with no expiry date are permanently discounted until manually removed."
            if lines else "No active discounts currently available."
        ),
    }


def transform_serey_apps(data) -> dict:
    """GET /api/v2/general/list-app"""
    items = data if isinstance(data, list) else (data.get("data") or data.get("apps") or [])
    names = [a.get("name", "") for a in items if a.get("name")]
    return {
        "title": "Serey Applications",
        "content": (
            f"Serey platform includes {len(names)} applications: {', '.join(names)}."
            if names else "Serey application list unavailable."
        ),
    }


def transform_marketplace_categories(data) -> dict:
    """GET /api/v2/general/list-marketplace-categories"""
    items = data if isinstance(data, list) else (data.get("data") or data.get("categories") or [])
    names = [c.get("name", "") for c in items if not c.get("deleted") and c.get("name")]
    return {
        "title": "Serey Marketplace Categories",
        "content": (
            f"Serey Marketplace has {len(names)} categories: {', '.join(names)}."
            if names else "Marketplace category data unavailable."
        ),
    }


def transform_global_properties(data) -> dict:
    """GET /api/v2/general/global-properties"""
    props = data.get("data") if isinstance(data, dict) else {}
    if not isinstance(props, dict):
        props = data if isinstance(data, dict) else {}
    supply = props.get("current_supply", "N/A")
    head = props.get("head_block_number", "N/A")
    witnesses = props.get("num_pow_witnesses", "N/A")
    return {
        "title": "Serey Blockchain Global Properties",
        "content": (
            f"Serey blockchain stats: current SEREY supply is {supply}, "
            f"head block number is {head}, active witnesses: {witnesses}."
        ),
    }


def transform_total_supply(data) -> dict:
    """GET /api/v2/general/total-supply"""
    inner = data.get("data") if isinstance(data, dict) else data
    supply = (
        (inner.get("total_supply") if isinstance(inner, dict) else None)
        or data.get("total_supply", "N/A")
    )
    return {
        "title": "SEREY Token Total Supply",
        "content": f"The total circulating supply of SEREY token is {supply}.",
    }


def transform_payment_methods(data) -> dict:
    """GET /api/v2/sereymarket/payment"""
    items = data.get("data") or data.get("results") or (data if isinstance(data, list) else [])
    lines = []
    for p in items:
        name = p.get("name") or p.get("payment_name", "")
        ptype = p.get("type") or p.get("payment_type", "")
        if name:
            lines.append(f"{name} ({ptype})" if ptype else name)
    return {
        "title": "Serey Marketplace Payment Methods",
        "content": (
            f"Serey Marketplace supports {len(lines)} payment methods: {', '.join(lines)}."
            if lines else "Payment method data unavailable."
        ),
    }


def transform_fundraising_categories(data) -> dict:
    """GET /api/v2/fundraising/get-categories  — response: {data: {result: [{name}]}}"""
    inner = data.get("data", {})
    items = (inner.get("result") if isinstance(inner, dict) else None) or (data if isinstance(data, list) else [])
    names = [c.get("name") or c.get("title", "") for c in items if isinstance(c, dict) and (c.get("name") or c.get("title"))]
    return {
        "title": "Serey Fundraising Categories",
        "content": (
            f"Serey supports {len(names)} fundraising campaign categories: {', '.join(names)}."
            if names else "Fundraising category data unavailable."
        ),
    }


def transform_popular_fundraisers(data) -> dict:
    """GET /api/v2/fundraising/get-popular-pagination"""
    items = data.get("data") or data.get("results") or (data if isinstance(data, list) else [])
    lines = []
    for f in items[:10]:
        title = f.get("title") or f.get("name", "")
        author = f.get("author", "")
        goal = f.get("goal_amount") or f.get("target_amount", "")
        if title:
            line = title
            if author:
                line += f" by @{author}"
            if goal:
                line += f" (goal: {goal})"
            lines.append(line)
    return {
        "title": "Popular Serey Fundraising Campaigns",
        "content": (
            f"Popular fundraising campaigns on Serey: {'; '.join(lines)}."
            if lines else "No popular fundraiser data available."
        ),
    }


def transform_country_list(data) -> dict:
    """GET /api/v2/country/list-countries"""
    items = data.get("data") or data.get("countries") or (data if isinstance(data, list) else [])
    names = [c.get("name") or c.get("country_name", "") for c in items if c.get("name") or c.get("country_name")]
    return {
        "title": "Countries in Serey System",
        "content": (
            f"Serey system supports {len(names)} countries: {', '.join(names)}."
            if names else "Country list data unavailable."
        ),
    }


def transform_subscription_plans(data) -> dict:
    """
    GET /api/v2/subscription/list-all-subscriptions
    Response: list or { data: [...] } of plan objects.

    Plan tiers (lowest → highest):
      basic_type1  — Landing Page, Online Shop
      basic_type2  — + Blog, Gallery, Media & Video, Fundraising, Marketplace, Micro Blog, Serey Link
      premium      — All components (premium)
      superhub     — All components (top-tier)

    Downgrading from premium/superhub to basic_type1 is blocked.
    """
    items = data if isinstance(data, list) else (data.get("subscriptions") or data.get("data") or data.get("plans") or [])
    if not isinstance(items, list):
        items = []

    # Group by region
    cambodia: list[str] = []
    international: list[str] = []

    for p in items:
        if not isinstance(p, dict):
            continue
        name = p.get("name", "")
        price = p.get("price", "")
        duration = p.get("duration", "")
        duration_type = p.get("duration_type", "")
        plan_type = p.get("plan_type", "")
        region = (p.get("region") or "").lower()
        components = p.get("allowed_components") or []

        comp_str = f", unlocks: {', '.join(components[:6])}{' +more' if len(components) > 6 else ''}" if components else ""
        line = f"{name} — ${price} / {duration} {duration_type} (tier: {plan_type}{comp_str})"

        if region == "cambodia":
            cambodia.append(line)
        else:
            international.append(line)

    parts = []
    parts.append(
        "Serey offers subscription plans with 4 tiers: basic_type1 (Landing Page + Online Shop), "
        "basic_type2 (adds Blog, Gallery, Media & Video, Fundraising, Marketplace, Micro Blog, Serey Link), "
        "premium (all components), and superhub (all components, top-tier). "
        "Downgrading from premium or superhub to basic_type1 is not allowed."
    )
    if cambodia:
        parts.append("Cambodia plans: " + "; ".join(cambodia) + ".")
    if international:
        parts.append("International plans: " + "; ".join(international) + ".")

    return {
        "title": "Serey Subscription Plans",
        "content": " ".join(parts) if (cambodia or international) else
            "Serey subscription plans data unavailable.",
    }


def transform_legacy_shop_categories(data) -> dict:
    """GET /api/v2/marketplace/list-online-shop-categories  — response: {categories: [{name, sub_categories[]}]}"""
    items = data.get("categories") or data.get("data") or (data if isinstance(data, list) else [])
    lines = []
    for c in items:
        if not isinstance(c, dict):
            continue
        name = c.get("name", "")
        subs = [s.get("name", "") for s in (c.get("sub_categories") or []) if s.get("name")]
        lines.append(f"{name} ({', '.join(subs)})" if subs else name)
    names = lines  # re-use variable for the return below
    return {
        "title": "Serey Online Shop Categories",
        "content": (
            f"Serey legacy online marketplace has {len(names)} shop categories: {', '.join(names)}."
            if names else "Legacy shop category data unavailable."
        ),
    }


def transform_legacy_products(data) -> dict:
    """GET /api/v2/marketplace/list-online-shop-product"""
    items = data.get("data") or data.get("results") or (data if isinstance(data, list) else [])
    lines = []
    for p in items[:30]:
        name = p.get("name") or p.get("title", "")
        price = p.get("price", "")
        if name:
            lines.append(f"{name} (${price})" if price else name)
    return {
        "title": "Serey Legacy Marketplace Products",
        "content": (
            f"Products listed on Serey legacy marketplace: {'; '.join(lines)}."
            if lines else "No legacy marketplace product data available."
        ),
    }
