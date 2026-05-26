from collections import Counter
from re import findall

from researchmate_api.services.store import ChunkEntry


# 提取中英文混合检索 token。
def tokenize(text: str) -> list[str]:
    return findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", text.lower())


# 使用轻量词频重合做本地检索，生产可替换为 Qdrant。
def retrieve_local_chunks(chunks: list[ChunkEntry], query: str, limit: int = 5) -> list[ChunkEntry]:
    query_tokens = Counter(tokenize(query))
    if not query_tokens:
        return chunks[:limit]
    scored: list[tuple[int, int, ChunkEntry]] = []
    for index, chunk in enumerate(chunks):
        chunk_tokens = Counter(tokenize(chunk.text))
        score = sum(min(query_tokens[token], chunk_tokens[token]) for token in query_tokens)
        scored.append((score, -index, chunk))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    positive = [chunk for score, _, chunk in scored if score > 0]
    return (positive or [chunk for _, _, chunk in scored])[:limit]


# 从 chunk 中生成安全短引用。
def snippet(text: str, length: int = 280) -> str:
    compact = " ".join(text.split())
    if len(compact) <= length:
        return compact
    return compact[: length - 1].rstrip() + "…"
