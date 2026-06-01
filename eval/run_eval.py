# Retrieval evaluation harness for the Serey knowledge base.
#
# Runs every query in retrieval_eval.json through the REAL search pipeline
# (services.search.search_serey_knowledge) and checks whether at least one
# expected chunk title appears in the retrieved context. This measures
# retrieval quality end-to-end: always-injected chunks, category-biased
# retrieval, the relevance threshold, and broad semantic search.
#
# Usage (from project root, with the venv active):
#   python eval/run_eval.py
#
# Prerequisite — the serey_knowledge collection must be indexed first:
#   python scripts/index_serey_knowledge.py   (static knowledge only)
#   or trigger POST /api/admin/sync-knowledge  (static + live data)
#
# Exit code is 0 if the hit rate meets PASS_THRESHOLD, else 1 (useful for CI).

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from services.search import search_serey_knowledge  # noqa: E402

EVAL_PATH = os.path.join(os.path.dirname(__file__), "retrieval_eval.json")
PASS_THRESHOLD = 0.85  # target hit rate; run "fails" (exit 1) below this


def _retrieved_titles(result: str) -> list[str]:
    """Pull the chunk titles out of the formatted '### Title\\ncontent' blocks."""
    return [line[4:].strip() for line in result.split("\n") if line.startswith("### ")]


def run() -> int:
    with open(EVAL_PATH, encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    passed = 0
    failures: list[tuple[str, list[str], list[str]]] = []
    by_domain: dict[str, list[int]] = {}

    for case in cases:
        query = case["query"]
        expect_any = case["expect_any"]
        domain = case.get("domain", "general")

        result = search_serey_knowledge(query)
        titles = _retrieved_titles(result)

        # Pass if any expected title substring appears in any retrieved title.
        hit = any(exp.lower() in t.lower() for exp in expect_any for t in titles)

        stats = by_domain.setdefault(domain, [0, 0])
        stats[1] += 1
        if hit:
            passed += 1
            stats[0] += 1
        else:
            failures.append((query, expect_any, titles))

    total = len(cases)
    rate = passed / total if total else 0.0

    print("=" * 66)
    print("SEREY KNOWLEDGE RETRIEVAL EVAL")
    print("=" * 66)
    print(f"Hit rate: {passed}/{total}  ({rate:.0%})")
    print()
    print("By domain:")
    for domain in sorted(by_domain):
        p, t = by_domain[domain]
        bar = "OK " if p == t else "!! "
        print(f"  {bar}{domain:<13} {p}/{t}")

    if failures:
        print()
        print(f"MISSES ({len(failures)}) — expected chunk not retrieved:")
        for query, expect, titles in failures:
            print(f"  Q: {query!r}")
            print(f"     wanted any of : {expect}")
            print(f"     got titles    : {titles}")

    print("=" * 66)
    if rate < PASS_THRESHOLD:
        print(f"RESULT: FAIL — hit rate {rate:.0%} is below target {PASS_THRESHOLD:.0%}")
        return 1
    print(f"RESULT: PASS — hit rate {rate:.0%} meets target {PASS_THRESHOLD:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
