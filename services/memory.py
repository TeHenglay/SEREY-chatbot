# Memory service — short-term (ChromaDB-persisted session) + long-term (ChromaDB user prefs).
#
# SHORT-TERM  — In-process deque as write-through cache, persisted to "session_turns"
#               ChromaDB collection. Survives server restarts. Sessions expire after 24h.
#
# LONG-TERM   — "user_memory" ChromaDB collection. uuid4 IDs (concurrency-safe).
#               Per-user cap of MAX_USER_MEMORIES; oldest entries pruned automatically.

import logging
import os
import time
import uuid
from collections import deque
from typing import Deque

import chromadb

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MAX_HISTORY_TURNS  = 20    # in-process deque cap per session (10 user + 10 assistant)
MAX_USER_MEMORIES  = 100   # long-term memories per user before oldest are pruned
SESSION_TTL_SECS   = 24 * 3600  # session turns older than this are not restored

# ---------------------------------------------------------------------------
# ChromaDB client
# ---------------------------------------------------------------------------
_CHROMA_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chroma_db")
)
_chroma = chromadb.PersistentClient(path=_CHROMA_PATH)


def _long_term_col():
    """Get-or-create the long-term user preference collection."""
    return _chroma.get_or_create_collection(
        "user_memory",
        metadata={"hnsw:space": "cosine"},
    )


def _session_col():
    """Get-or-create the session-turn persistence collection."""
    return _chroma.get_or_create_collection(
        "session_turns",
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Short-term memory — in-process deque + ChromaDB write-through persistence
# ---------------------------------------------------------------------------
# Maps session_id -> deque of (role, text) tuples, loaded lazily from ChromaDB on miss.
_session_cache: dict[str, Deque[tuple[str, str]]] = {}


def _load_session_from_disk(session_id: str) -> Deque[tuple[str, str]]:
    """Warm the in-process deque from ChromaDB (on server restart)."""
    dq: Deque[tuple[str, str]] = deque(maxlen=MAX_HISTORY_TURNS)
    try:
        col = _session_col()
        result = col.get(
            where={"session_id": session_id},
            include=["documents", "metadatas"],
        )
        if not result["ids"]:
            return dq
        cutoff = time.time() - SESSION_TTL_SECS
        # Collect valid turns and sort by turn_idx for correct ordering
        turns: list[tuple[int, str, str]] = []
        for doc, meta in zip(result["documents"], result["metadatas"]):
            if meta.get("created_at", 0) < cutoff:
                continue  # expired — skip
            turns.append((int(meta.get("turn_idx", 0)), meta["role"], doc))
        turns.sort(key=lambda t: t[0])
        for _, role, text in turns:
            dq.append((role, text))
    except Exception as e:
        logger.warning("Failed to load session from disk: %s", e)
    return dq


def _get_session_deque(session_id: str) -> Deque[tuple[str, str]]:
    if session_id not in _session_cache:
        _session_cache[session_id] = _load_session_from_disk(session_id)
    return _session_cache[session_id]


def append_session_turn(session_id: str, user_message: str, assistant_reply: str) -> None:
    """Write turn to in-process cache AND persist to ChromaDB."""
    dq = _get_session_deque(session_id)
    # turn_idx: sequential position so ordering is preserved after reload
    base_idx = len(dq)
    dq.append(("user", user_message))
    dq.append(("assistant", assistant_reply))
    try:
        col = _session_col()
        now = time.time()
        col.add(
            ids=[str(uuid.uuid4()), str(uuid.uuid4())],
            documents=[user_message, assistant_reply],
            metadatas=[
                {"session_id": session_id, "role": "user",      "created_at": now, "turn_idx": base_idx},
                {"session_id": session_id, "role": "assistant",  "created_at": now, "turn_idx": base_idx + 1},
            ],
        )
    except Exception as e:
        logger.warning("Failed to persist session turn: %s", e)


def get_session_history_prompt(session_id: str) -> str:
    """Return conversation history as a formatted string. Empty string if none."""
    dq = _get_session_deque(session_id)
    if not dq:
        return ""
    lines = []
    for role, text in dq:
        prefix = "User" if role == "user" else "Serey Assistant"
        lines.append(f"{prefix}: {text}")
    return "\n".join(lines)


def prune_expired_sessions() -> None:
    """Delete session turn records older than SESSION_TTL_SECS. Safe to call periodically."""
    try:
        col = _session_col()
        cutoff = time.time() - SESSION_TTL_SECS
        col.delete(where={"created_at": {"$lt": cutoff}})
        logger.info("Pruned expired session turns (cutoff=%.0f)", cutoff)
    except Exception as e:
        logger.warning("Failed to prune expired session turns: %s", e)


# ---------------------------------------------------------------------------
# Long-term memory — ChromaDB persistent user preferences
# ---------------------------------------------------------------------------

def save_interaction(user_id: str, session_id: str, content: str) -> None:
    """Persist a memory entry. uuid4 ID is concurrency-safe.
    Prunes oldest entries if user exceeds MAX_USER_MEMORIES."""
    try:
        col = _long_term_col()
        col.add(
            ids=[str(uuid.uuid4())],
            documents=[content],
            metadatas=[{
                "user_id": user_id,
                "session_id": session_id,
                "created_at": time.time(),
            }],
        )
        _prune_user_memories(col, user_id)
    except Exception as e:
        logger.warning("Failed to save memory: %s", e)


def _prune_user_memories(col, user_id: str) -> None:
    """Keep only the latest MAX_USER_MEMORIES entries for a user."""
    try:
        result = col.get(
            where={"user_id": user_id},
            include=["metadatas"],
        )
        ids = result["ids"]
        if len(ids) <= MAX_USER_MEMORIES:
            return
        pairs = list(zip(ids, result["metadatas"]))
        pairs.sort(key=lambda x: x[1].get("created_at", 0))  # oldest first
        to_delete = [p[0] for p in pairs[: len(ids) - MAX_USER_MEMORIES]]
        col.delete(ids=to_delete)
        logger.info("Pruned %d old memories for user %s", len(to_delete), user_id)
    except Exception as e:
        logger.warning("Failed to prune user memories: %s", e)


def get_user_preferences(user_id: str, query: str, n_results: int = 5) -> str:
    """Semantic search over a user's long-term memories.
    Returns formatted string for prompt injection."""
    try:
        col = _long_term_col()
        total = col.count()
        if total == 0:
            return "No previous preferences recorded."
        n = min(n_results, total)
        results = col.query(
            query_texts=[query],
            n_results=n,
            where={"user_id": user_id},
            include=["documents"],
        )
        docs = results["documents"][0] if results["documents"] else []
        if not docs:
            return "No previous preferences recorded."
        return "\n".join(f"- {d}" for d in docs)
    except Exception as e:
        logger.warning("Failed to retrieve user memories: %s", e)
        return "No previous preferences recorded."


def get_session_context(session_id: str, query: str, n_results: int = 5) -> str:
    """Semantic search over long-term memories stored for a specific session."""
    try:
        col = _long_term_col()
        total = col.count()
        if total == 0:
            return "No prior context in this session."
        n = min(n_results, total)
        results = col.query(
            query_texts=[query],
            n_results=n,
            where={"session_id": session_id},
            include=["documents"],
        )
        docs = results["documents"][0] if results["documents"] else []
        if not docs:
            return "No prior context in this session."
        return "\n".join(f"- {d}" for d in docs)
    except Exception as e:
        logger.warning("Failed to retrieve session memories: %s", e)
        return "No prior context in this session."


def clear_session(session_id: str) -> None:
    """Remove a session from cache and both ChromaDB collections."""
    _session_cache.pop(session_id, None)
    for col_fn, label in [(_session_col, "session_turns"), (_long_term_col, "user_memory")]:
        try:
            col_fn().delete(where={"session_id": session_id})
        except Exception as e:
            logger.warning("Failed to clear %s for session %s: %s", label, session_id, e)
