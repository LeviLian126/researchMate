"""Coordinate bounded reranking providers with deterministic degradation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

from researchmate_api.config import Settings
from researchmate_api.schemas.common import SourceType
from researchmate_api.services.qdrant_store import QdrantHybridStore, VectorStoreRequestError
from researchmate_api.services.retrieval import RetrievalCandidate

RerankProviderName = Literal["qdrant", "nvidia", "deterministic"]


class RerankRequestError(RuntimeError):
    """Identify which rerank provider failed."""

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(message)
        self.provider = provider


@dataclass(frozen=True)
class RerankResult:
    """Return ranked candidates with provider and degradation metadata."""

    candidates: list[RetrievalCandidate]
    provider: RerankProviderName
    model: str | None
    degraded: bool
    fallback_reason: str | None = None


class Reranker(Protocol):
    """Define the shared owner-aware reranker contract."""

    name: RerankProviderName
    model: str | None

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        *,
        top_n: int,
        user_id: str,
        project_id: str,
    ) -> list[RetrievalCandidate]: ...


class DeterministicReranker:
    """Provide a network-free stable fallback ranking."""

    name: RerankProviderName = "deterministic"
    model = None

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        *,
        top_n: int,
        user_id: str,
        project_id: str,
    ) -> list[RetrievalCandidate]:
        """Sort candidates deterministically using existing retrieval scores."""
        del query, user_id, project_id
        return sorted(
            candidates,
            key=lambda item: (
                item.score,
                item.lexical_rank is not None,
                -(item.lexical_rank or 10_000),
            ),
            reverse=True,
        )[:top_n]


class NvidiaReranker:
    """Adapt NVIDIA's ranking API to retrieval candidates."""

    name: RerankProviderName = "nvidia"

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.model = settings.nvidia_rerank_model
        self.client = client or httpx.Client(
            base_url=settings.nvidia_rerank_base_url.rstrip("/"),
            timeout=settings.rerank_timeout_seconds,
            headers={
                "Authorization": (
                    f"Bearer {settings.nvidia_api_key.get_secret_value()}"
                    if settings.nvidia_api_key
                    else ""
                ),
                "Content-Type": "application/json",
            },
        )

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        *,
        top_n: int,
        user_id: str,
        project_id: str,
    ) -> list[RetrievalCandidate]:
        """Return provider-ranked candidates from the supplied allowlist."""
        del user_id, project_id
        if not self.settings.nvidia_api_key:
            raise RerankRequestError(self.name, "NVIDIA reranking is not configured")
        try:
            response = self.client.post(
                "/v1/ranking",
                json={
                    "model": self.model,
                    "query": {"text": query},
                    "passages": [{"text": item.chunk.text} for item in candidates],
                    "top_n": top_n,
                    "truncate": "END",
                },
            )
            response.raise_for_status()
            rankings = response.json().get("rankings", response.json().get("results", []))
            indices = [
                int(item["index"])
                for item in rankings
                if isinstance(item, dict) and isinstance(item.get("index"), int)
            ]
        except Exception as exc:
            raise RerankRequestError(self.name, "NVIDIA reranking failed") from exc
        ordered = [candidates[index] for index in indices if 0 <= index < len(candidates)]
        if not ordered:
            raise RerankRequestError(self.name, "NVIDIA reranking returned no candidates")
        return ordered[:top_n]


class QdrantNativeReranker:
    """Use the verified Qdrant late-interaction collection for reranking."""

    name: RerankProviderName = "qdrant"

    def __init__(self, settings: Settings, store: QdrantHybridStore) -> None:
        self.settings = settings
        self.store = store
        self.model = settings.qdrant_rerank_model

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        *,
        top_n: int,
        user_id: str,
        project_id: str,
    ) -> list[RetrievalCandidate]:
        """Return Qdrant-ranked candidates while preserving owner scope."""
        if not self.model or not self.settings.qdrant_rerank_model_is_free:
            raise RerankRequestError(
                self.name, "Qdrant reranking requires a verified free late-interaction model"
            )
        try:
            ids = self.store.rerank_query(
                user_id=user_id,
                project_id=project_id,
                text=query,
                candidate_ids=[str(item.chunk.id) for item in candidates],
                model=self.model,
                limit=top_n,
            )
        except VectorStoreRequestError as exc:
            raise RerankRequestError(self.name, "Qdrant reranking failed") from exc
        by_id = {str(item.chunk.id): item for item in candidates}
        ordered = [by_id[chunk_id] for chunk_id in ids if chunk_id in by_id]
        if not ordered:
            raise RerankRequestError(self.name, "Qdrant reranking returned no candidates")
        return ordered


class RerankCoordinator:
    """Select providers and degrade safely when optional reranking fails."""

    def __init__(
        self,
        settings: Settings,
        *,
        qdrant: QdrantHybridStore | None,
        nvidia_client: Any | None = None,
    ) -> None:
        self.settings = settings
        self.deterministic = DeterministicReranker()
        self.qdrant = QdrantNativeReranker(settings, qdrant) if qdrant else None
        self.nvidia = NvidiaReranker(settings, client=nvidia_client)

    def execute(
        self,
        provider: Literal["auto", "qdrant", "nvidia", "deterministic"],
        query: str,
        candidates: list[RetrievalCandidate],
        *,
        user_id: str,
        project_id: str,
        top_n: int | None = None,
    ) -> RerankResult:
        """Execute the requested provider chain and report any fallback."""
        if not candidates:
            return RerankResult([], "deterministic", None, False)
        order: list[Reranker]
        if provider == "qdrant":
            order = [item for item in (self.qdrant, self.nvidia) if item is not None]
        elif provider == "nvidia":
            order = [item for item in (self.nvidia, self.qdrant) if item is not None]
        elif provider == "deterministic":
            order = [self.deterministic]
        else:
            order = [item for item in (self.qdrant, self.nvidia) if item is not None]
        if any(item.chunk.source_type == SourceType.WEB_PAGE for item in candidates):
            order = [item for item in order if item.name != "qdrant"]
        failures: list[str] = []
        result_limit = top_n or self.settings.rerank_top_n
        for reranker in order:
            try:
                ranked = reranker.rerank(
                    query,
                    candidates,
                    top_n=result_limit,
                    user_id=user_id,
                    project_id=project_id,
                )
                return RerankResult(
                    ranked,
                    reranker.name,
                    reranker.model,
                    degraded=bool(failures),
                    fallback_reason="; ".join(failures) or None,
                )
            except RerankRequestError as exc:
                failures.append(f"{exc.provider}_unavailable")
        ranked = self.deterministic.rerank(
            query,
            candidates,
            top_n=result_limit,
            user_id=user_id,
            project_id=project_id,
        )
        return RerankResult(
            ranked,
            "deterministic",
            None,
            degraded=provider != "deterministic",
            fallback_reason="; ".join(failures) or "provider_not_configured",
        )
