"""Provide deterministic text chunking used by indexing jobs."""

from __future__ import annotations


# Pure-function chunker for reuse in tests by the local worker and API adapter.
def chunk_text_for_index(text: str, target_size: int = 900) -> list[str]:
    """Split normalized text into bounded chunks without dropping content."""
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []
    chunks: list[str] = []
    current = ""
    for paragraph in normalized.split("\n"):
        if len(current) + len(paragraph) + 1 <= target_size:
            current = f"{current}\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks
