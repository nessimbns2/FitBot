"""
scripts/rag_smoke.py
RAG Smoke test: evaluate retrieval hit rate at k=5 against tests/rag_questions.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.rag_core.engine import get_vector_store


def main():
    root = Path(__file__).resolve().parent.parent
    questions_file = root / "tests" / "rag_questions.json"
    if not questions_file.exists():
        print(f"Error: {questions_file} not found.")
        return

    with open(questions_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    store = get_vector_store()

    hits = 0
    misses = []

    print(f"Running RAG smoke test with {len(questions)} questions at k=5...\n")

    for i, item in enumerate(questions, 1):
        q = item["question"]
        cat = item["category"]
        expected = item["expected_source"]

        try:
            results = store.search(q, category=cat, k=5, min_score=0.1)
            sources = [r.source for r in results]

            if expected in sources:
                hits += 1
                rank = sources.index(expected) + 1
                print(f"[{i:02d}] PASS (Rank {rank}): '{q[:50]}...' -> {expected}")
            else:
                misses.append({
                    "index": i,
                    "question": q,
                    "category": cat,
                    "expected": expected,
                    "retrieved": sources,
                })
                print(f"[{i:02d}] MISS: '{q[:50]}...' -> Expected: {expected}, Got: {sources}")
        except Exception as e:
            misses.append({
                "index": i,
                "question": q,
                "category": cat,
                "expected": expected,
                "error": str(e),
            })
            print(f"[{i:02d}] ERROR: '{q[:50]}...' -> {e}")

    hit_rate = (hits / len(questions)) * 100.0
    print("\n" + "=" * 50)
    print(f"Smoke Test Summary: {hits}/{len(questions)} ({hit_rate:.1f}% hit rate)")
    print("=" * 50)

    if misses:
        print("\nMiss Details:")
        for m in misses:
            print(f"- Question #{m['index']}: {m['question']}")
            print(f"  Expected: {m['expected']}")
            if "retrieved" in m:
                print(f"  Retrieved: {m['retrieved']}")
            else:
                print(f"  Error: {m.get('error')}")


if __name__ == "__main__":
    main()
