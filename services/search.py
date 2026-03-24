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
    ready to inject into a prompt."""
    try:
        collection = _get_knowledge_collection()
    except RuntimeError as e:
        logger.warning("Serey knowledge search skipped: %s", str(e))
        return "No Serey knowledge available."

    count = collection.count()
    n = min(n_results, count)
    if n == 0:
        return "No Serey knowledge available."

    results = collection.query(query_texts=[query], n_results=n)
    chunks = []

    # Always inject routing and explicit structure chunks to guarantee accurate links
    try:
        route_results = collection.get(ids=["serey_routes", "serey_social_media"])
        if route_results and route_results["metadatas"]:
            for metadata in route_results["metadatas"]:
                chunks.append(f"### {metadata['title']}\n{metadata['content']}")
                logger.info("Auto-injected baseline chunk: %s", metadata['title'])
    except Exception as e:
        logger.warning("Failed to auto-inject routing chunk: %s", str(e))

    for metadata in results["metadatas"][0]:
        if metadata.get("id") not in ["serey_routes", "serey_social_media"]:
            chunks.append(f"### {metadata['title']}\n{metadata['content']}")
            logger.info("Retrieved knowledge chunk: %s", metadata.get("title", "Unknown"))

    return "\n\n".join(chunks)
