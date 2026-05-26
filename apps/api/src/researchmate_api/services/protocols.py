from typing import Protocol


# 定义 Embedding provider 抽象，后续由 NVIDIA/Jina/Voyage 实现。
class EmbeddingProvider(Protocol):
    # 批量生成文本向量。
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a batch of texts."""


# 定义 Search provider 抽象，后续由 Serper/Tavily 实现。
class SearchProvider(Protocol):
    # 执行联网搜索并返回排序结果。
    def search(self, query: str, limit: int) -> list[dict]:
        """Return ranked search results."""


# 定义 URL reader 抽象，后续由 Jina/Firecrawl 实现。
class UrlReader(Protocol):
    # 读取网页并返回脱敏快照。
    def read(self, url: str) -> dict:
        """Return a sanitized page snapshot."""


# 定义向量库抽象，后续由 Qdrant 实现。
class VectorStore(Protocol):
    # 按用户、项目和来源过滤检索 chunks。
    def query(self, user_id: str, project_id: str, source_type: str, text: str) -> list[dict]:
        """Return source-filtered chunks."""
