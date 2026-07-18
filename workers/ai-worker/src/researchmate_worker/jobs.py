# 纯函数 chunker，供本地 worker 与 API adapter 复用测试。
def chunk_text_for_index(text: str, target_size: int = 900) -> list[str]:
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
