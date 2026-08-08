"""Provide deterministic text chunking for local ingestion and tests."""

from __future__ import annotations

from researchmate_api.schemas.common import SNIPPET_CHUNK


def chunk_text(text: str, target_size: int = SNIPPET_CHUNK) -> list[str]:
    """Split normalized text into bounded, traceable chunks."""
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []
    paragraphs = normalized.split("\n")
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= target_size:
            current = f"{current}\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
            while len(current) > target_size:
                chunks.append(current[:target_size].strip())
                current = current[target_size:].strip()
    if current:
        chunks.append(current)
    return chunks
