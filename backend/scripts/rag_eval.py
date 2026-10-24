"""
backend/scripts/rag_eval.py
Evaluates RAG retrieval precision, category isolation, and semantic relevance
across 20 comprehensive questions in tests/rag_eval.json.
"""

import json
import sys
from pathlib import Path

# Add backend to sys.path
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app.core.config import settings
from app.modules.rag_core.engine import VectorStore, SentenceTransformerEmbedder


def run_eval():
    eval_file = backend_root / "tests" / "rag_eval.json"
    if not eval_file.exists():
        print(f"Error: {eval_file} not found.")
        sys.exit(1)

    with open(eval_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = data.get("questions", [])
    print(f"Loaded {len(questions)} evaluation questions.")

    embedder = SentenceTransformerEmbedder(model_name=settings.EMBEDDING_MODEL)
    vector_store = VectorStore(
        vectorstore_dir=Path(settings.VECTORSTORE_DIR),
        embedder=embedder,
    )

    total = len(questions)
    passed_isolation = 0
    keyword_hits = 0
    reciprocal_ranks = []
    scores = []

    print("-" * 75)
    print(f"{'ID':<12} | {'Category':<10} | {'Isolation':<10} | {'Kw Match':<10} | {'Top Score':<10}")
    print("-" * 75)

    for item in questions:
        qid = item["id"]
        cat = item["category"]
        query = item["query"]
        expected_kws = item.get("expected_keywords", [])

        # Retrieve top 5 chunks strictly from this category
        results = vector_store.search(
            query=query,
            category=cat,
            k=5,
            min_score=0.10,
        )

        # 1. Isolation check
        wrong_cat_chunks = [r for r in results if r.category != cat]
        isolation_ok = (len(wrong_cat_chunks) == 0)
        if isolation_ok:
            passed_isolation += 1

        # 2. Keyword presence in any retrieved chunk
        combined_text = " ".join(r.text.lower() for r in results)
        matched_any = any(kw.lower() in combined_text for kw in expected_kws)
        if matched_any:
            keyword_hits += 1

        # 3. Reciprocal Rank (rank of first chunk matching any keyword)
        rr = 0.0
        for rank, r in enumerate(results, start=1):
            if any(kw.lower() in r.text.lower() for kw in expected_kws):
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

        top_score = results[0].score if results else 0.0
        scores.append(top_score)

        print(
            f"{qid:<12} | {cat:<10} | {'PASS' if isolation_ok else 'FAIL':<10} | "
            f"{'YES' if matched_any else 'NO':<10} | {top_score:.3f}"
        )

    mrr = sum(reciprocal_ranks) / total if total > 0 else 0.0
    avg_score = sum(scores) / total if total > 0 else 0.0
    hit_rate = (keyword_hits / total) * 100.0
    iso_rate = (passed_isolation / total) * 100.0

    print("=" * 75)
    print(f"RAG Evaluation Summary:")
    print(f"Total Queries Evaluated:    {total}")
    print(f"Category Isolation Rate:    {iso_rate:.1f}% ({passed_isolation}/{total})")
    print(f"Semantic Keyword Hit Rate:  {hit_rate:.1f}% ({keyword_hits}/{total})")
    print(f"Mean Reciprocal Rank (MRR): {mrr:.3f}")
    print(f"Average Top-1 Score:        {avg_score:.3f}")
    print("=" * 75)

    if iso_rate < 100.0 or hit_rate < 80.0:
        print("FAILED: Evaluation metrics below acceptable quality gate.")
        sys.exit(1)
    else:
        print("SUCCESS: All RAG quality gates passed.")


if __name__ == "__main__":
    run_eval()
