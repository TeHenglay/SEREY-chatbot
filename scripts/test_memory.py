# Comprehensive memory round-trip tests — 6 tests covering long-term and short-term memory.
# Run from the backend/ directory: python scripts/test_memory.py

import sys
import os
import time
import uuid

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

# Use timestamped IDs so each test run is isolated from previous runs
RUN = str(int(time.time()))
USER_A   = f"test_user_{RUN}"
SESSION_A = f"test_session_{RUN}_a"
SESSION_B = f"test_session_{RUN}_b"

from services.memory import (
    save_interaction,
    get_user_preferences,
    get_session_context,
    append_session_turn,
    get_session_history_prompt,
    _session_cache,
    MAX_USER_MEMORIES,
)

results: list[tuple[str, bool]] = []


def check(name: str, passed: bool) -> None:
    status = "PASS" if passed else "FAIL"
    print(f"  {status}")
    results.append((name, passed))


# ---------------------------------------------------------------------------
# Test 1: Long-term preferences are stored and semantically retrieved
# ---------------------------------------------------------------------------
print("\n--- Test 1: Long-term preferences ---")
save_interaction(USER_A, SESSION_A, "User asked: Build a dark themed landing page.")
save_interaction(USER_A, SESSION_A, "User asked: Add rounded buttons and blue accents.")
save_interaction(USER_A, SESSION_A, "User asked: Make the hero section full-screen.")
prefs = get_user_preferences(USER_A, "landing page design preferences")
print(f"  {prefs}")
check("Long-term preferences", "dark" in prefs.lower() or "blue" in prefs.lower() or "rounded" in prefs.lower())

# ---------------------------------------------------------------------------
# Test 2: Session context retrieves memories scoped to SESSION_A
# ---------------------------------------------------------------------------
print("\n--- Test 2: Session context for session A ---")
ctx_a = get_session_context(SESSION_A, "landing page")
print(f"  {ctx_a}")
check("Session A context non-empty", ctx_a != "No prior context in this session.")

# ---------------------------------------------------------------------------
# Test 3: Session B has no memories (isolation)
# ---------------------------------------------------------------------------
print("\n--- Test 3: Session isolation (session B has no memories) ---")
ctx_b = get_session_context(SESSION_B, "landing page")
print(f"  {ctx_b}")
check("Session B isolated", ctx_b == "No prior context in this session.")

# ---------------------------------------------------------------------------
# Test 4: Concurrent-safe saves — all entries appear (uuid4 IDs, no collisions)
# ---------------------------------------------------------------------------
print("\n--- Test 4: Concurrent-safe saves (20 rapid writes) ---")
CONCURRENT_USER = f"concurrent_user_{RUN}"
for i in range(20):
    save_interaction(CONCURRENT_USER, SESSION_A, f"Rapid memory entry #{i}")

# Count how many made it in
import chromadb, os as _os
_chroma_path = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "chroma_db"))
_chroma = chromadb.PersistentClient(path=_chroma_path)
col = _chroma.get_or_create_collection("user_memory")
saved = col.get(where={"user_id": CONCURRENT_USER}, include=["metadatas"])
count = len(saved["ids"])
print(f"  Saved {count}/20 entries (no collisions expected)")
check("All 20 entries stored without collision", count == 20)

# ---------------------------------------------------------------------------
# Test 5: Short-term session history survives simulated server restart
# ---------------------------------------------------------------------------
print("\n--- Test 5: short-term session persists across restart ---")
RESTART_SESSION = f"restart_session_{RUN}"
append_session_turn(RESTART_SESSION, "Hello, my name is Dara.", "Nice to meet you, Dara!")
append_session_turn(RESTART_SESSION, "What is the Serey marketplace?", "It is a digital marketplace.")

# Simulate restart: evict only this session from in-process cache
_session_cache.pop(RESTART_SESSION, None)

# Re-read — must warm from ChromaDB
prompt = get_session_history_prompt(RESTART_SESSION)
print(f"  {repr(prompt[:120])}...")
check("Session warmed from disk after restart", "Dara" in prompt)

# ---------------------------------------------------------------------------
# Test 6: Per-user memory cap prunes oldest entries
# ---------------------------------------------------------------------------
print(f"\n--- Test 6: Memory cap (MAX_USER_MEMORIES={MAX_USER_MEMORIES}) ---")
CAP_USER = f"cap_user_{RUN}"
OVER = MAX_USER_MEMORIES + 5
for i in range(OVER):
    save_interaction(CAP_USER, SESSION_A, f"Memory entry {i:03d}")

after = col.get(where={"user_id": CAP_USER}, include=["metadatas"])
final_count = len(after["ids"])
print(f"  Wrote {OVER} entries → stored {final_count} (cap={MAX_USER_MEMORIES})")
check(f"Memory count capped at {MAX_USER_MEMORIES}", final_count <= MAX_USER_MEMORIES)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 40)
passed = sum(1 for _, ok in results if ok)
print(f"Results: {passed}/{len(results)} passed")
for name, ok in results:
    print(f"  {'✓' if ok else '✗'} {name}")
