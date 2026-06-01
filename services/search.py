# ChromaDB search service for retrieving relevant component and Serey knowledge embeddings.
# Raises RuntimeError if the collections haven't been indexed yet.

import chromadb
import json
import logging
import os

logger = logging.getLogger(__name__)

# Use absolute path so this works regardless of the working directory
_CHROMA_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chroma_db"))
_client = chromadb.PersistentClient(path=_CHROMA_PATH)

try:
    _collection = _client.get_collection("components")
except Exception:
    _collection = None
    logger.warning(
        "ChromaDB 'components' collection not found. "
        "Run: python scripts/index_components.py"
    )

# Note: serey_knowledge collection is NOT cached — knowledge_sync.py deletes
# and recreates it on every sync, so a cached object would have a stale UUID.
# _client.get_collection() is a fast metadata lookup and safe to call per-request.


def _get_collection():
    global _collection
    if _collection is None:
        try:
            _collection = _client.get_collection("components")
        except Exception:
            raise RuntimeError(
                "Components not indexed. Run: python scripts/index_components.py"
            )
    return _collection


def search_components(query: str, n_results: int = 4) -> list[dict]:
    """Return the most relevant components from ChromaDB for the given query."""
    collection = _get_collection()
    count = collection.count()
    n = min(n_results, count)
    if n == 0:
        return []

    results = collection.query(query_texts=[query], n_results=n)
    components = []
    for metadata in results["metadatas"][0]:
        comp = {
            "name": metadata["name"],
            "example": json.loads(metadata["example_json"]),
        }
        components.append(comp)
        logger.info("Retrieved component: %s", metadata["name"])
    return components


def get_all_component_names() -> list[str]:
    """Return names of all indexed components."""
    collection = _get_collection()
    results = collection.get(include=["metadatas"])
    return [m["name"] for m in results["metadatas"]]


# ---------------------------------------------------------------------------
# Serey knowledge search
# ---------------------------------------------------------------------------

# Chunks always injected regardless of query — kept intentionally small (~600 chars each).
_ALWAYS_INJECT_IDS = {"serey_routes_core", "serey_social_media"}

# Cosine distance thresholds: chunks with distance > the threshold are dropped.
# Empirically, good matches score 0.3-0.75 and noise scores 0.77+.
#  - BROAD search (no domain filter) uses the strict threshold to keep noise out.
#  - CATEGORY-confirmed results use a looser threshold: the category filter already
#    guarantees the chunk is in the right domain, so a mediocre embedding score is
#    still trustworthy (e.g. "what is your email address" → support chunk at 0.77).
_SIMILARITY_THRESHOLD = 0.75
_CATEGORY_THRESHOLD = 0.85

# Keyword → category hint for domain-biased retrieval.
# Only map keywords where category filtering clearly helps — don't add "quiz", "blog",
# "gallery" etc. here since those routes live in the "navigation" category, not "platform".
# Unrecognised queries fall through to pure broad semantic search.
_CATEGORY_HINTS: list[tuple[list[str], str]] = [
    (["shop", "product", "price", "buy", "sell", "order", "cart", "checkout", "marketplace", "seller", "discount"], "marketplace"),
    (["community", "group", "join", "cambodia", "netherlands", "usa", "club"], "community"),
    (["earn", "commission", "referral", "equity", "creator", "investor", "invest", "phantom"], "earning"),
    (["weather", "temperature", "rain", "forecast", "climate"], "general"),
    (["payment", "bank", "aba", "wing", "pay", "transfer", "money", "wallet"], "payments"),
    (["support", "help", "contact", "email", "telegram"], "support"),
    (["about", "founder", "found", "create", "made", "behind", "ceo", "owner", "history", "story", "mission", "traction"], "about"),
]


def _detect_category(query: str) -> str | None:
    q = query.lower()
    for keywords, category in _CATEGORY_HINTS:
        if any(kw in q for kw in keywords):
            return category
    return None


def _reset_knowledge_client() -> None:
    """Recreate the shared ChromaDB client to discard a stale collection reference.
    A sync deletes and recreates the serey_knowledge collection; that can leave this
    process's client pointing at a now-deleted collection UUID, raising
    'Collection [...] does not exist' on the next query. Rebuilding the client fixes it."""
    global _client, _collection
    try:
        _client = chromadb.PersistentClient(path=_CHROMA_PATH)
        _collection = None
        logger.info("Reset ChromaDB client after a stale-collection error.")
    except Exception as e:
        logger.warning("Failed to reset ChromaDB client: %s", e)


def _get_knowledge_collection():
    """Always fetch fresh — sync recreates the collection on every run."""
    try:
        return _client.get_collection("serey_knowledge")
    except Exception:
        raise RuntimeError(
            "Serey knowledge not indexed. Run POST /api/admin/sync-knowledge"
        )


def search_serey_knowledge(query: str, n_results: int = 8) -> str:
    """Semantic search over the Serey knowledge base.
    Returns a formatted string of the most relevant knowledge chunks
    ready to inject into a prompt.

    Strategy:
    1. Always inject serey_routes_core + serey_social_media (core nav context, by ID).
    2. If query matches a keyword hint, run a category-filtered query first (up to 3
       results) using the looser _CATEGORY_THRESHOLD — the category filter already
       guarantees domain relevance.
    3. Fill remaining slots with broad semantic search (strict _SIMILARITY_THRESHOLD).
    Total semantic slots: MAX_SEMANTIC (7) + 2 always-injected = 9 max chunks in prompt.
    The n_results arg is kept for backward compatibility but MAX_SEMANTIC governs the cap.

    Wrapped in a reset+retry: a re-index/sync can leave the shared client with a stale
    collection handle, so on the first failure we rebuild the client and retry once
    rather than silently returning empty results.
    """
    for attempt in range(2):
        try:
            return _do_knowledge_search(query)
        except RuntimeError as e:
            # Collection not indexed yet — retrying won't help.
            logger.warning("Serey knowledge search skipped: %s", str(e))
            return "No Serey knowledge available."
        except Exception as e:
            if attempt == 0:
                logger.warning("Knowledge search failed (%s); resetting client and retrying.", e)
                _reset_knowledge_client()
                continue
            logger.error("Knowledge search failed after retry: %s", e)
            return "No Serey knowledge available."
    return "No Serey knowledge available."


def _do_knowledge_search(query: str) -> str:
    """Inner implementation. Lets ChromaDB errors propagate so the wrapper can
    reset the client and retry — do not swallow exceptions here."""
    collection = _get_knowledge_collection()
    count = collection.count()
    if count == 0:
        return "No Serey knowledge available."

    chunks: list[str] = []
    seen_ids: set[str] = set()
    MAX_SEMANTIC = 7  # max semantic chunks; + 2 always-injected = 9 total in prompt

    # --- Step 1: Always-inject baseline chunks (by ID) ---
    route_results = collection.get(ids=list(_ALWAYS_INJECT_IDS))
    if route_results and route_results["metadatas"]:
        for metadata in route_results["metadatas"]:
            chunks.append(f"### {metadata['title']}\n{metadata['content']}")
            seen_ids.add(metadata.get("id", ""))
            logger.info("Auto-injected baseline chunk: %s", metadata['title'])

    def _add_from_results(metadatas: list, distances: list, max_add: int, threshold: float) -> int:
        """Add up to max_add chunks scoring within `threshold`. Returns number added."""
        added = 0
        for metadata, distance in zip(metadatas, distances):
            if added >= max_add:
                break
            chunk_id = metadata.get("id", "")
            if chunk_id in seen_ids:
                continue
            if distance > threshold:
                logger.debug("Dropped low-relevance chunk %s (distance=%.3f)", chunk_id, distance)
                continue
            chunks.append(f"### {metadata['title']}\n{metadata['content']}")
            seen_ids.add(chunk_id)
            logger.info("Retrieved chunk: %s (distance=%.3f)", metadata.get("title", "Unknown"), distance)
            added += 1
        return added

    semantic_added = 0

    # --- Step 2: Category-biased retrieval (if hint detected) ---
    category_hint = _detect_category(query)
    if category_hint:
        n_cat = min(3, count)
        cat_results = collection.query(
            query_texts=[query],
            n_results=n_cat,
            where={"category": category_hint},
            include=["metadatas", "distances"],
        )
        semantic_added += _add_from_results(
            cat_results["metadatas"][0], cat_results["distances"][0],
            MAX_SEMANTIC - semantic_added, _CATEGORY_THRESHOLD,
        )
        logger.info("Category-biased retrieval: hint=%s, added=%d", category_hint, semantic_added)

    # --- Step 3: Broad semantic search to fill remaining slots ---
    slots_left = MAX_SEMANTIC - semantic_added
    if slots_left > 0:
        n_broad = min(slots_left + len(seen_ids), count)
        broad_results = collection.query(
            query_texts=[query],
            n_results=n_broad,
            include=["metadatas", "distances"],
        )
        semantic_added += _add_from_results(
            broad_results["metadatas"][0], broad_results["distances"][0],
            slots_left, _SIMILARITY_THRESHOLD,
        )

    return "\n\n".join(chunks)
