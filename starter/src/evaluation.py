"""Evaluate retrieved evidence and preserve per-query traces."""
import unicodedata
from typing import Any


def normalize_text_for_match(text: str) -> str:
    """Normalize text and collapse all whitespace to single spaces for robust quote matching."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFC", text)
    return " ".join(norm.split())


def evaluate_query(
    question: dict[str, Any], hits: list[dict[str, Any]]
) -> dict[str, Any]:
    """Check source/page and whether enough gold evidence is captured.

    Accepts documented gold evidence. Records Hit@1 and Hit@3 status.
    """
    gold_source = question.get("gold_source_id", "")
    gold_page = question.get("gold_page")
    raw_quote = question.get("evidence_quote", "")
    gold_quote = normalize_text_for_match(raw_quote)

    evaluated_hits: list[dict[str, Any]] = []
    first_hit_rank: int | None = None

    for rank, hit in enumerate(hits, start=1):
        hit_doc = hit.get("document_id", "")
        hit_page = hit.get("page")
        hit_text_norm = normalize_text_for_match(hit.get("text", ""))

        is_source_match = hit_doc == gold_source
        is_page_match = hit_page == gold_page
        is_evidence_match = gold_quote in hit_text_norm if gold_quote else False

        # A hit requires matching gold document, valid gold page, and containing the evidence
        is_hit = is_source_match and is_page_match and is_evidence_match

        if is_hit and first_hit_rank is None:
            first_hit_rank = rank

        evaluated_hits.append({
            "rank": rank,
            "chunk_id": hit.get("chunk_id"),
            "document_id": hit_doc,
            "source": hit.get("source"),
            "page": hit_page,
            "score": hit.get("score"),
            "text": hit.get("text"),
            "metadata": hit.get("metadata", {}),
            "is_source_match": is_source_match,
            "is_page_match": is_page_match,
            "is_evidence_match": is_evidence_match,
            "is_gold_hit": is_hit,
        })

    is_hit_at_1 = first_hit_rank == 1
    is_hit_at_3 = first_hit_rank is not None and first_hit_rank <= 3

    return {
        "question_id": question.get("id"),
        "split": question.get("split"),
        "type": question.get("type"),
        "question": question.get("question"),
        "expected_answer": question.get("expected_answer"),
        "gold_source_id": gold_source,
        "gold_page": gold_page,
        "evidence_quote": raw_quote,
        "filter_applied": question.get("filter"),
        "first_hit_rank": first_hit_rank,
        "hit_at_1": is_hit_at_1,
        "hit_at_3": is_hit_at_3,
        "hits": evaluated_hits,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    summary: dict[str, Any] = {}

    # Group traces by strategy
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for t in traces:
        strat = t.get("strategy", "unknown")
        by_strategy.setdefault(strat, []).append(t)

    for strat, strat_traces in by_strategy.items():
        summary[strat] = {}
        for split_name in ["dev", "test", "overall"]:
            if split_name == "overall":
                split_traces = strat_traces
            else:
                split_traces = [
                    t for t in strat_traces if t.get("split") == split_name
                ]

            total = len(split_traces)
            if total == 0:
                summary[strat][split_name] = {
                    "count": 0,
                    "hit_at_1": "N/A",
                    "hit_at_3": "N/A",
                }
                continue

            hit1_count = sum(1 for t in split_traces if t.get("hit_at_1"))
            hit3_count = sum(1 for t in split_traces if t.get("hit_at_3"))

            summary[strat][split_name] = {
                "count": total,
                "hit_at_1_ratio": f"{hit1_count}/{total}",
                "hit_at_1_percent": round((hit1_count / total) * 100, 2),
                "hit_at_3_ratio": f"{hit3_count}/{total}",
                "hit_at_3_percent": round((hit3_count / total) * 100, 2),
            }

    return summary
