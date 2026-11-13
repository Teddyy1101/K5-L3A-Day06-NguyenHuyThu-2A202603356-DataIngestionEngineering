"""Execute Day 06 Data Ingestion Pipeline for Strategies A, B, and C."""
import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load env variables
env_file = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_file if env_file.exists() else None)

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .ingestion import load_pdf
from .store import PgVectorStore


def main() -> None:
    print("=" * 60)
    print("DAY 06 - DATA INGESTION ENGINEERING PIPELINE")
    print("=" * 60)

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://day6:day6_local_only@127.0.0.1:55433/day6_lab",
    )
    pdf_path = Path("starter/data/progit.pdf")
    doc_id = "progit-v2"
    source = "data/progit.pdf"

    # Step 1: Read and normalize PDF
    print("\n[Step 1/5] Ingesting PDF pages (19 to 65)...")
    start_time = time.time()
    pages = load_pdf(
        path=pdf_path,
        document_id=doc_id,
        source=source,
        start_page=19,
        end_page=65,
        min_chars=150,
        log_path=Path("results/ingestion_log.json"),
    )
    print(f"  Loaded {len(pages)} valid pages.")

    # Step 2: Initialize Embedding Model & Vector Store
    print("\n[Step 2/5] Initializing OpenAI Embedder & PostgreSQL + pgvector...")
    embedder = MyEmbedder()
    store = PgVectorStore(database_url=db_url, dimensions=embedder.dimensions)
    store.create_schema()
    print(
        f"  Embedder model: {embedder.model_name} (dim={embedder.dimensions})"
    )
    print("  Database schema initialized successfully.")

    # Step 3: Chunking for Strategy A and Strategy B
    print("\n[Step 3/5] Generating chunks...")
    chunks_a = []
    for p in pages:
        chunks_a.extend(fixed_size(p, size=500, overlap=50))
    print(f"  Strategy A (fixed_size 500/50): {len(chunks_a)} chunks")

    chunks_b = []
    for p in pages:
        chunks_b.extend(by_paragraph(p, max_size=600))
    print(f"  Strategy B/C (by_paragraph <=600): {len(chunks_b)} chunks")

    # Step 4: Generating Embeddings and Upserting to Database
    print(
        "\n[Step 4/5] Embedding chunks and storing in PostgreSQL + pgvector..."
    )

    # Strategy A
    t0_a = time.time()
    print("  Embedding Strategy A chunks...")
    texts_a = [c.text for c in chunks_a]
    vectors_a = embedder.embed_documents(texts_a)
    store.upsert(strategy="A", chunks=chunks_a, vectors=vectors_a)
    time_a = time.time() - t0_a
    count_a = store.count_chunks("A")
    print(f"  -> Strategy A stored: {count_a} chunks in {time_a:.2f}s")

    # Strategy B (also serves Strategy C)
    t0_b = time.time()
    print("  Embedding Strategy B chunks...")
    texts_b = [c.text for c in chunks_b]
    vectors_b = embedder.embed_documents(texts_b)
    store.upsert(strategy="B", chunks=chunks_b, vectors=vectors_b)
    time_b = time.time() - t0_b
    count_b = store.count_chunks("B")
    print(f"  -> Strategy B stored: {count_b} chunks in {time_b:.2f}s")

    # Step 5: Verify Idempotency (Re-ingesting does not duplicate)
    print("\n[Step 5/5] Verifying Idempotency (Re-ingest check)...")
    store.upsert(strategy="B", chunks=chunks_b, vectors=vectors_b)
    count_b_after = store.count_chunks("B")
    print(f"  Chunk count before: {count_b} | after re-ingest: {count_b_after}")
    idempotent_ok = count_b == count_b_after
    print(
        f"  Idempotency verification: {'PASSED (No duplicates)' if idempotent_ok else 'FAILED'}"
    )

    total_pipeline_time = time.time() - start_time
    total_tokens = embedder.total_tokens_used
    total_cost_usd = embedder.get_estimated_cost_usd()

    stats = {
        "timestamp": datetime.now().isoformat(),
        "total_pipeline_time_seconds": round(total_pipeline_time, 2),
        "embedding_model": embedder.model_name,
        "embedding_dimensions": embedder.dimensions,
        "total_tokens_used": total_tokens,
        "estimated_cost_usd": round(total_cost_usd, 6),
        "idempotency_verified": idempotent_ok,
        "strategies": {
            "A": {
                "chunk_count": count_a,
                "ingest_time_seconds": round(time_a, 2),
            },
            "B": {
                "chunk_count": count_b,
                "ingest_time_seconds": round(time_b, 2),
            },
            "C": {
                "chunk_count": count_b,
                "note": "Shares B chunks/embeddings; applies metadata filter at retrieval",
            },
        },
    }

    stats_path = Path("results/ingest_stats.json")
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print("\nPipeline execution summary saved to results/ingest_stats.json:")
    print(json.dumps(stats, indent=2))
    print("\nSTAGE 4 COMPLETE!")


if __name__ == "__main__":
    main()
