from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import UUID, uuid5

from researchmate_api.config import Settings
from researchmate_api.schemas.common import SourceType
from researchmate_api.services.store import ChunkEntry


WEB_EVIDENCE_NAMESPACE = UUID("7fe3d3f1-a008-4f54-93c6-743ca8a2c349")


class HttpClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any: ...


class WebSearchRequestError(RuntimeError):
    def __init__(self, *, retryable: bool) -> None:
        super().__init__("Web search provider request failed")
        self.retryable = retryable


class TavilyWebSearchProvider:
    """Bounded Tavily adapter that returns untrusted text as evidence, never instructions."""

    def __init__(self, settings: Settings, client: HttpClient | None = None) -> None:
        if settings.web_search_provider != "tavily" or settings.tavily_api_key is None:
            raise ValueError("Tavily web search is not configured")
        self.settings = settings
        if client is None:
            import httpx

            client = httpx.Client(timeout=settings.web_search_timeout_seconds)
        self.client = client

    def search(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        query: str,
        limit: int = 5,
    ) -> list[ChunkEntry]:
        bounded_limit = max(1, min(5, limit))
        try:
            response = self.client.post(
                f"{self.settings.tavily_base_url.rstrip('/')}/search",
                headers={
                    "Authorization": f"Bearer {self.settings.tavily_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                    "X-Project-ID": "researchmate",
                },
                json={
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": False,
                    "include_raw_content": "text",
                    "include_images": False,
                    "max_results": bounded_limit,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            raise WebSearchRequestError(
                retryable=isinstance(exc, (TimeoutError, ConnectionError))
                or status_code in {408, 409, 429, 500, 502, 503, 504}
            ) from exc

        raw_results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(raw_results, list):
            raise WebSearchRequestError(retryable=False)
        chunks: list[ChunkEntry] = []
        for item in raw_results[:bounded_limit]:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            title = item.get("title")
            content = item.get("raw_content") or item.get("content")
            if not self._safe_url(url) or not isinstance(content, str) or not content.strip():
                continue
            safe_text = content.strip()[:6000]
            stable_key = f"{project_id}:{url}:{safe_text}"
            chunks.append(
                ChunkEntry(
                    id=uuid5(WEB_EVIDENCE_NAMESPACE, stable_key),
                    user_id=user_id,
                    project_id=project_id,
                    document_id=None,
                    source_type=SourceType.WEB_PAGE,
                    source_title=(title.strip()[:300] if isinstance(title, str) else url),
                    text=safe_text,
                    url=url,
                )
            )
        return chunks

    @staticmethod
    def _safe_url(value: Any) -> bool:
        if not isinstance(value, str) or len(value) > 2048:
            return False
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
