"""Implement fixed-size and structure-aware (paragraph) chunking."""
import re
from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Split text into overlapping windows of fixed character length and retain page metadata.

    Strategy A.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")

    text = page.text
    if not text:
        return []

    chunks: list[Chunk] = []
    step = size - overlap
    start = 0
    idx = 0

    while start < len(text):
        end = min(start + size, len(text))
        chunk_text = text[start:end].strip()

        if chunk_text:
            chunk_id = f"A_{page.document_id}_p{page.page}_c{idx:03d}"
            chunk_meta = dict(page.metadata)
            chunk_meta.update({
                "strategy": "A",
                "chunk_index": idx,
                "char_length": len(chunk_text),
                "start_char": start,
                "end_char": end,
            })
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=chunk_text,
                    metadata=chunk_meta,
                )
            )
            idx += 1

        if end >= len(text):
            break
        start += step

    return chunks


def by_paragraph(page: DocumentPage, max_size: int = 600, min_chunk_size: int = 40) -> list[Chunk]:
    """Group paragraphs, split oversized paragraphs and retain metadata.

    Strategies B & C. Merges trailing tiny fragments to maintain semantic coherence.
    """
    if max_size <= 0:
        raise ValueError("max_size must be positive")

    text = page.text
    if not text:
        return []

    # Split into raw paragraphs by double newline
    raw_paras = [p.strip() for p in text.split("\n\n") if p.strip()]

    # If single paragraph exceeds max_size, break by sentence or line
    refined_units: list[str] = []
    for para in raw_paras:
        if len(para) <= max_size:
            refined_units.append(para)
        else:
            # Split oversized paragraph by sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            current_unit = ""
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                if len(s) > max_size:
                    for sub_idx in range(0, len(s), max_size):
                        sub = s[sub_idx : sub_idx + max_size].strip()
                        if sub:
                            refined_units.append(sub)
                    continue

                if not current_unit:
                    current_unit = s
                elif len(current_unit) + 1 + len(s) <= max_size:
                    current_unit = f"{current_unit} {s}"
                else:
                    refined_units.append(current_unit)
                    current_unit = s
            if current_unit:
                refined_units.append(current_unit)

    # Greedily pack refined_units into chunks up to max_size
    packed_texts: list[str] = []
    current_chunk = ""

    for unit in refined_units:
        if not current_chunk:
            current_chunk = unit
        elif len(current_chunk) + 2 + len(unit) <= max_size:
            current_chunk = f"{current_chunk}\n\n{unit}"
        else:
            packed_texts.append(current_chunk)
            current_chunk = unit

    if current_chunk:
        # If the last fragment is very small and previous chunk exists, merge if possible or keep
        if len(current_chunk) < min_chunk_size and packed_texts:
            last_text = packed_texts[-1]
            if len(last_text) + 2 + len(current_chunk) <= max_size * 1.15:
                packed_texts[-1] = f"{last_text}\n\n{current_chunk}"
            else:
                packed_texts.append(current_chunk)
        else:
            packed_texts.append(current_chunk)

    chunks: list[Chunk] = []
    for idx, c_text in enumerate(packed_texts):
        chunk_id = f"B_{page.document_id}_p{page.page}_c{idx:03d}"
        chunk_meta = dict(page.metadata)
        chunk_meta.update({
            "strategy": "B",
            "chunk_index": idx,
            "char_length": len(c_text),
        })
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                document_id=page.document_id,
                source=page.source,
                page=page.page,
                text=c_text,
                metadata=chunk_meta,
            )
        )

    return chunks
