"""Test ingestion and chunking strategies; output comparative statistics."""
import json
import statistics
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starter.src.ingestion import load_pdf
from starter.src.chunking import fixed_size, by_paragraph


def main():
    pdf_path = Path("starter/data/progit.pdf")
    doc_id = "progit-v2"
    source = "data/progit.pdf"

    print("Step 1: Running load_pdf()...")
    pages = load_pdf(
        path=pdf_path,
        document_id=doc_id,
        source=source,
        start_page=19,
        end_page=65,
        min_chars=150,
        log_path=Path("results/ingestion_log.json"),
    )
    print(f"Loaded {len(pages)} valid pages.")

    print("\nStep 2: Generating chunks for Strategy A (fixed_size: size=500, overlap=50)...")
    chunks_a = []
    for p in pages:
        chunks_a.extend(fixed_size(p, size=500, overlap=50))
    print(f"Strategy A generated {len(chunks_a)} chunks.")

    print("\nStep 3: Generating chunks for Strategy B (by_paragraph: max_size=600)...")
    chunks_b = []
    for p in pages:
        chunks_b.extend(by_paragraph(p, max_size=600))
    print(f"Strategy B generated {len(chunks_b)} chunks.")

    # Calculate statistics
    lengths_a = [len(c.text) for c in chunks_a]
    lengths_b = [len(c.text) for c in chunks_b]

    stats = {
        "valid_pages_count": len(pages),
        "total_source_chars": sum(len(p.text) for p in pages),
        "strategy_a_fixed_size": {
            "chunk_count": len(chunks_a),
            "size_param": 500,
            "overlap_param": 50,
            "min_length": min(lengths_a),
            "max_length": max(lengths_a),
            "mean_length": round(statistics.mean(lengths_a), 2),
            "median_length": statistics.median(lengths_a),
            "total_chars": sum(lengths_a),
        },
        "strategy_b_by_paragraph": {
            "chunk_count": len(chunks_b),
            "max_size_param": 600,
            "min_length": min(lengths_b),
            "max_length": max(lengths_b),
            "mean_length": round(statistics.mean(lengths_b), 2),
            "median_length": statistics.median(lengths_b),
            "total_chars": sum(lengths_b),
        },
    }

    stats_path = Path("results/chunking_stats.json")
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print(f"\nStats written to {stats_path}:")
    print(json.dumps(stats, indent=2))

    # Verify metadata preservation
    sample_a = chunks_a[0]
    sample_b = chunks_b[0]
    print("\nSample Chunk A metadata:", sample_a.metadata)
    print("Sample Chunk B metadata:", sample_b.metadata)
    assert "chapter" in sample_a.metadata and "chapter" in sample_b.metadata
    assert sample_a.document_id == doc_id and sample_b.document_id == doc_id
    print("\nMetadata integrity assertion passed!")


if __name__ == "__main__":
    main()
