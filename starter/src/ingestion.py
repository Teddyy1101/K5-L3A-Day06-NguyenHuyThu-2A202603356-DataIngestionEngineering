"""Read and normalize source data with traceability and error logging."""
import json
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
import pypdf

from .models import DocumentPage

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize Unicode (NFC) and whitespace without discarding useful structure."""
    if not text:
        return ""

    # 1. Unicode NFC normalization
    norm = unicodedata.normalize("NFC", text)

    # 2. Replace non-breaking spaces and other special spaces
    norm = norm.replace("\xa0", " ").replace("\u200b", "")

    # 3. Normalize carriage returns
    norm = norm.replace("\r\n", "\n").replace("\r", "\n")

    # 4. Collapse consecutive horizontal whitespace (spaces, tabs) into a single space
    # but preserve paragraph breaks (\n\n)
    lines = norm.split("\n")
    cleaned_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]

    # 5. Join lines while preserving intentional blank lines (paragraph breaks)
    # Consecutive blank lines (>2) collapsed into two newlines
    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def load_pdf(
    path: Path,
    document_id: str,
    source: str,
    start_page: int = 19,
    end_page: int = 65,
    min_chars: int = 150,
    log_path: Path | None = None,
) -> list[DocumentPage]:
    """Extract each physical page within the specified range; keep page number and source.

    Detects and logs short/empty pages. Retains metadata including chapter.
    """
    if not path.exists():
        raise FileNotFoundError(f"Source PDF not found at {path}")

    reader = pypdf.PdfReader(path)
    total_physical_pages = len(reader.pages)

    actual_start = max(1, start_page)
    actual_end = min(total_physical_pages, end_page)

    valid_pages: list[DocumentPage] = []
    excluded_pages: list[dict[str, Any]] = []

    for p_num in range(actual_start, actual_end + 1):
        try:
            raw_text = reader.pages[p_num - 1].extract_text() or ""
        except Exception as e:
            logger.warning(f"Error reading page {p_num}: {e}")
            excluded_pages.append({"page": p_num, "reason": f"extract_error: {str(e)}"})
            continue

        normalized_text = normalize_text(raw_text)
        char_count = len(normalized_text)

        if char_count < min_chars:
            excluded_pages.append({
                "page": p_num,
                "reason": f"too_short_{char_count}_chars",
                "char_count": char_count,
            })
            continue

        # Extract structured metadata (Chapter distinction)
        # In Pro Git: Pages 19-32 are Chapter 1 (Getting Started); 33-65 are Chapter 2 (Git Basics)
        chapter = "ch01_getting_started" if p_num <= 32 else "ch02_git_basics"

        doc_page = DocumentPage(
            document_id=document_id,
            source=source,
            page=p_num,
            text=normalized_text,
            metadata={"chapter": chapter, "char_count": char_count},
        )
        valid_pages.append(doc_page)

    # Save detailed ingestion log
    if log_path is None:
        log_path = Path("results/ingestion_log.json")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "document_id": document_id,
        "source_path": str(path),
        "total_physical_pages": total_physical_pages,
        "target_range": [actual_start, actual_end],
        "valid_pages_count": len(valid_pages),
        "excluded_pages_count": len(excluded_pages),
        "valid_page_numbers": [p.page for p in valid_pages],
        "excluded_pages": excluded_pages,
        "total_normalized_chars": sum(len(p.text) for p in valid_pages),
    }

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    return valid_pages
