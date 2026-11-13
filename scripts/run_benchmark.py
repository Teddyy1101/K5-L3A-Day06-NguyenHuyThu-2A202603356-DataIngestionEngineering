"""Benchmark execution script for Strategies A, B, and C with full trace saving."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starter.src.embeddings import MyEmbedder
from starter.src.evaluation import evaluate_query, summarize
from starter.src.store import PgVectorStore


def main():
    print("=" * 65)
    print("RUNNING BENCHMARK EVALUATION (STRATEGIES A, B, C)")
    print("=" * 65)

    questions_path = Path("benchmark/questions.json")
    if not questions_path.exists():
        sys.exit(f"Error: Questions file not found at {questions_path}")

    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Loaded {len(questions)} questions from {questions_path}")
    dev_q = [q for q in questions if q.get("split") == "dev"]
    test_q = [q for q in questions if q.get("split") == "test"]
    print(f"  Dev questions: {len(dev_q)} | Test questions: {len(test_q)}")

    # Initialize store and embedder
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://day6:day6_local_only@127.0.0.1:55433/day6_lab",
    )
    embedder = MyEmbedder()
    store = PgVectorStore(database_url=db_url, dimensions=embedder.dimensions)

    all_traces = []

    # Execute for Strategy A, B, and C
    strategies = [
        {"name": "A", "store_strategy": "A", "use_filter": False},
        {"name": "B", "store_strategy": "B", "use_filter": False},
        {"name": "C", "store_strategy": "B", "use_filter": True},
    ]

    for strat_info in strategies:
        strat_name = strat_info["name"]
        store_strat = strat_info["store_strategy"]
        use_filter = strat_info["use_filter"]

        print(
            f"\nRunning Strategy {strat_name} (store={store_strat}, use_filter={use_filter})..."
        )

        for q in questions:
            q_text = q["question"]
            q_vec = embedder.embed_query(q_text)

            filters = q.get("filter") if use_filter else None
            hits = store.search(
                strategy=store_strat,
                query_vector=q_vec,
                top_k=3,
                filters=filters,
            )

            eval_result = evaluate_query(q, hits)
            eval_result["strategy"] = strat_name
            all_traces.append(eval_result)

    # Save traces
    traces_path = Path("results/traces.json")
    traces_path.parent.mkdir(parents=True, exist_ok=True)
    with open(traces_path, "w", encoding="utf-8") as f:
        json.dump(all_traces, f, indent=2, ensure_ascii=False)
    print(
        f"\nAll {len(all_traces)} query traces saved to: {traces_path}"
    )

    # Summarize metrics
    summary = summarize(all_traces)
    summary_path = Path("results/metrics_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Metrics summary saved to: {summary_path}")

    # Print markdown table summary
    print("\n" + "=" * 65)
    print("BENCHMARK RETRIEVAL METRICS SUMMARY")
    print("=" * 65)
    print(
        f"{'Strategy':<10} | {'Split':<6} | {'Hit@1 (n/N)':<12} | {'Hit@1 (%)':<10} | {'Hit@3 (n/N)':<12} | {'Hit@3 (%)':<10}"
    )
    print("-" * 75)
    for strat in ["A", "B", "C"]:
        for split in ["dev", "test", "overall"]:
            s = summary.get(strat, {}).get(split, {})
            print(
                f"{strat:<10} | {split:<6} | {s.get('hit_at_1_ratio', ''):<12} | {s.get('hit_at_1_percent', 0):<10} | {s.get('hit_at_3_ratio', ''):<12} | {s.get('hit_at_3_percent', 0):<10}"
            )
    print("=" * 75)


if __name__ == "__main__":
    main()

