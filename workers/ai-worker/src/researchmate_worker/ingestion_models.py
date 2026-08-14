"""Define ingestion events, parsed records, failures, and worker adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel
from researchmate_api.services.store import ChunkEntry


class IngestionEvent(BaseModel):
    """Validate identifiers for one durable ingestion delivery."""

    job_id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID


@dataclass(frozen=True)
class IngestionRecord:
    """Carry the claimed document and object metadata needed for ingestion."""

    job_id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID
    filename: str
    file_type: str
    r2_object_key: str
    checksum_sha256: str | None
    attempts: int


@dataclass(frozen=True)
class ParsedBlock:
    """Carry normalized text with stable structural provenance."""

    text: str
    page_no: int | None = None
    slide_no: int | None = None
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PageProjection:
    """Carry page-level text assembled for durable source display."""

    id: UUID
    page_no: int | None
    slide_no: int | None
    section_title: str | None
    text: str
    metadata: dict[str, Any]


class ParserAdapterError(RuntimeError):
    """Normalize parser failures without leaking library-specific errors."""

    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class IngestionFailure(RuntimeError):
    """Expose a stable ingestion failure code and retry classification."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class DocumentParser(Protocol):
    """Define bounded document parsing independent of a conversion library."""

    def parse(self, source: Path, *, file_type: str) -> list[ParsedBlock]: ...


class ObjectReader(Protocol):
    """Define scoped object download independent of a storage SDK."""

    def download_to_file(self, object_key: str, destination: Path) -> None: ...


class VectorProjection(Protocol):
    """Define chunk projection independent of a vector database SDK."""

    def upsert_chunks(self, chunks: list[ChunkEntry], *, pipeline_version: str) -> None: ...


class WikiCompiler(Protocol):
    """Define LLM-powered wiki compilation independent of a chat provider SDK."""

    def compile(
        self,
        chunks: list[ChunkEntry],
        *,
        filename: str,
        user_id: UUID,
        project_id: UUID,
        document_id: UUID,
    ) -> list[ChunkEntry]: ...

    def compile_overview(
        self,
        chunks: list[ChunkEntry],
        *,
        filename: str,
        user_id: UUID,
        project_id: UUID,
        document_id: UUID,
    ) -> list[ChunkEntry]: ...


class IngestionStore(Protocol):
    """Define lease-safe ingestion persistence and terminal transitions."""

    def claim(
        self, event: IngestionEvent, *, worker_id: str, lease_seconds: int
    ) -> IngestionRecord | None: ...

    def replace_content(
        self,
        record: IngestionRecord,
        *,
        worker_id: str,
        pages: list[PageProjection],
        chunks: list[ChunkEntry],
        pipeline_version: str,
    ) -> None: ...

    def mark_ready(self, record: IngestionRecord, *, worker_id: str) -> None: ...

    def mark_retryable(self, record: IngestionRecord, *, worker_id: str, code: str) -> None: ...

    def mark_failed(self, record: IngestionRecord, *, worker_id: str, code: str) -> None: ...
