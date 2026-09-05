"""Coordinate object download, parsing, projection, indexing, and terminal job state."""

from __future__ import annotations

import logging
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from researchmate_api.services.object_storage import ObjectStorageRequestError
from researchmate_api.services.qdrant_store import VectorStoreRequestError
from researchmate_api.services.retrieval import estimate_tokens
from researchmate_api.services.store import ChunkEntry

from researchmate_worker.ingestion_models import (
    DocumentParser,
    IngestionEvent,
    IngestionFailure,
    IngestionRecord,
    IngestionStore,
    ObjectReader,
    ParserAdapterError,
    VectorProjection,
    WikiCompiler,
    WikiProjectState,
)
from researchmate_worker.ingestion_projections import build_projections

LOGGER = logging.getLogger(__name__)


class DocumentIngestionService:
    """Coordinate download, parse, project, and index transitions for one document."""

    def __init__(
        self,
        *,
        store: IngestionStore,
        object_reader: ObjectReader,
        parser: DocumentParser,
        vector_projection: VectorProjection,
        pipeline_version: str,
        lease_seconds: int,
        max_attempts: int,
        max_upload_bytes: int,
        lightweight_token_threshold: int = 4000,
        wiki_compiler: WikiCompiler | None = None,
    ) -> None:
        self.store = store
        self.object_reader = object_reader
        self.parser = parser
        self.vector_projection = vector_projection
        self.pipeline_version = pipeline_version
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.max_upload_bytes = max_upload_bytes
        self.lightweight_token_threshold = lightweight_token_threshold
        self.wiki_compiler = wiki_compiler

    def is_lightweight_corpus(self, chunks: list[ChunkEntry]) -> bool:
        """Return True when total chunk tokens are at or below the lightweight threshold."""
        total_tokens = sum(estimate_tokens(chunk.text) for chunk in chunks)
        return total_tokens <= self.lightweight_token_threshold

    def handle(self, event: IngestionEvent, *, worker_id: str) -> str:
        """Execute one claimed ingestion delivery and persist a safe terminal outcome."""
        record = self.store.claim(event, worker_id=worker_id, lease_seconds=self.lease_seconds)
        if record is None:
            return "not_claimed"
        try:
            with TemporaryDirectory(prefix="researchmate-ingest-") as directory:
                source = Path(directory) / f"source.{record.file_type}"
                LOGGER.info(
                    "ingestion_download_started document_id=%s file_type=%s",
                    record.document_id,
                    record.file_type,
                )
                self.object_reader.download_to_file(record.r2_object_key, source)
                LOGGER.info(
                    "ingestion_download_completed document_id=%s size_bytes=%s",
                    record.document_id,
                    source.stat().st_size,
                )
                if source.stat().st_size > self.max_upload_bytes:
                    raise IngestionFailure("DOCUMENT_TOO_LARGE", retryable=False)
                actual_checksum = sha256(source.read_bytes()).hexdigest()
                if record.checksum_sha256 and actual_checksum != record.checksum_sha256:
                    raise IngestionFailure("CHECKSUM_MISMATCH", retryable=False)
                LOGGER.info(
                    "ingestion_parse_started document_id=%s file_type=%s",
                    record.document_id,
                    record.file_type,
                )
                blocks = self.parser.parse(source, file_type=record.file_type)
                LOGGER.info(
                    "ingestion_parse_completed document_id=%s block_count=%s",
                    record.document_id,
                    len(blocks),
                )
            pages, chunks = build_projections(
                record,
                blocks,
                pipeline_version=self.pipeline_version,
            )
            LOGGER.info(
                "ingestion_projections_built document_id=%s pages=%s chunks=%s",
                record.document_id,
                len(pages),
                len(chunks),
            )
            if not pages or not chunks:
                raise IngestionFailure("NO_EXTRACTABLE_TEXT", retryable=False)

            raw_chunks = chunks
            is_lightweight = self.is_lightweight_corpus(raw_chunks)

            if is_lightweight:
                LOGGER.info(
                    "ingestion_lightweight_skip_vector document_id=%s token_count=%s",
                    record.document_id,
                    sum(estimate_tokens(c.text) for c in chunks),
                )
                for chunk in raw_chunks:
                    chunk.has_vector = False
            else:
                LOGGER.info(
                    "ingestion_embedding_started document_id=%s chunk_count=%s",
                    record.document_id,
                    len(raw_chunks),
                )
                self.vector_projection.upsert_chunks(
                    raw_chunks, pipeline_version=self.pipeline_version
                )
                LOGGER.info(
                    "ingestion_embedding_completed document_id=%s",
                    record.document_id,
                )
                for chunk in raw_chunks:
                    chunk.has_vector = True

            wiki_state = self._load_wiki_state(record)
            wiki_chunks = self._compile_wiki_index(raw_chunks, record, wiki_state)
            for chunk in wiki_chunks or []:
                chunk.has_vector = False
                chunk.metadata = {
                    **chunk.metadata,
                    "wiki_mode": True,
                    "knowledge_role": "wiki_index",
                    "wiki_index_version": "v2",
                }
            for chunk in raw_chunks:
                chunk.metadata = {
                    **chunk.metadata,
                    "knowledge_role": "raw_evidence",
                    "retrieval_tier": "lightweight" if is_lightweight else "vector",
                }
            chunks = raw_chunks

            LOGGER.info(
                "ingestion_persist_started document_id=%s",
                record.document_id,
            )
            if callable(getattr(self.store, "load_wiki_state", None)):
                self.store.replace_content(
                    record,
                    worker_id=worker_id,
                    pages=pages,
                    chunks=chunks,
                    pipeline_version=self.pipeline_version,
                    wiki_chunks=wiki_chunks,
                    base_knowledge_generation=wiki_state.knowledge_generation,
                    recovered_wiki_generation=(
                        wiki_state.wiki_generation if wiki_chunks is not None else None
                    ),
                )
            else:
                self.store.replace_content(
                    record,
                    worker_id=worker_id,
                    pages=pages,
                    chunks=[*chunks, *(wiki_chunks or [])],
                    pipeline_version=self.pipeline_version,
                )
            self.store.mark_ready(record, worker_id=worker_id)
            return "succeeded"
        except ObjectStorageRequestError as exc:
            self._record_failure(record, worker_id, "OBJECT_STORAGE_UNAVAILABLE", exc.retryable)
            raise IngestionFailure("OBJECT_STORAGE_UNAVAILABLE", retryable=exc.retryable) from exc
        except VectorStoreRequestError as exc:
            self._record_failure(record, worker_id, "VECTOR_STORE_UNAVAILABLE", exc.retryable)
            raise IngestionFailure("VECTOR_STORE_UNAVAILABLE", retryable=exc.retryable) from exc
        except ParserAdapterError as exc:
            self._record_failure(record, worker_id, exc.code, exc.retryable)
            raise IngestionFailure(exc.code, retryable=exc.retryable) from exc
        except IngestionFailure as exc:
            self._record_failure(record, worker_id, exc.code, exc.retryable)
            raise
        except SoftTimeLimitExceeded as exc:
            self._record_failure(record, worker_id, "INGESTION_TIMEOUT", True)
            raise IngestionFailure("INGESTION_TIMEOUT", retryable=True) from exc
        except Exception as exc:
            LOGGER.exception(
                "ingestion_unexpected_error document_id=%s error=%s",
                record.document_id,
                type(exc).__name__,
            )
            self._record_failure(record, worker_id, "INGESTION_INTERNAL_ERROR", False)
            raise IngestionFailure("INGESTION_INTERNAL_ERROR", retryable=False) from exc

    def _load_wiki_state(self, record: IngestionRecord) -> WikiProjectState:
        """Load canonical project state when the store supports incremental Wiki writes."""
        loader = getattr(self.store, "load_wiki_state", None)
        if callable(loader):
            return cast(WikiProjectState, loader(record))
        return WikiProjectState()

    def _compile_wiki_index(
        self,
        chunks: list[ChunkEntry],
        record: IngestionRecord,
        wiki_state: WikiProjectState,
    ) -> list[ChunkEntry] | None:
        """Build non-vector Wiki index entries without making ingestion depend on the LLM."""
        if self.wiki_compiler is None:
            return None
        try:
            compile_index = self.wiki_compiler.compile_index
            if callable(getattr(self.store, "load_wiki_state", None)):
                existing = {chunk.id: chunk for chunk in wiki_state.chunks}
                affected: dict[UUID, ChunkEntry] = {}
                pending: dict[UUID, list[ChunkEntry]] = {}
                for chunk in wiki_state.pending_chunks:
                    if chunk.document_id is not None and chunk.document_id != record.document_id:
                        pending.setdefault(chunk.document_id, []).append(chunk)
                for pending_document_id, pending_chunks in pending.items():
                    recovered = compile_index(
                        pending_chunks,
                        filename=pending_chunks[0].source_title,
                        user_id=record.user_id,
                        project_id=record.project_id,
                        document_id=pending_document_id,
                        existing_chunks=list(existing.values()),
                        generation=wiki_state.knowledge_generation + 1,
                    )
                    self._merge_compiled_chunks(existing, affected, recovered)
                latest = compile_index(
                    chunks,
                    filename=record.filename,
                    user_id=record.user_id,
                    project_id=record.project_id,
                    document_id=record.document_id,
                    existing_chunks=list(existing.values()),
                    generation=wiki_state.knowledge_generation + 1,
                )
                self._merge_compiled_chunks(existing, affected, latest)
                compiled = list(affected.values())
            else:
                compiled = compile_index(
                    chunks,
                    filename=record.filename,
                    user_id=record.user_id,
                    project_id=record.project_id,
                    document_id=record.document_id,
                )
            if compiled is not None:
                LOGGER.info(
                    "ingestion_wiki_compiled document_id=%s pages=%s",
                    record.document_id,
                    len(compiled),
                )
                return compiled
        except Exception as exc:
            LOGGER.warning(
                "wiki_compilation_failed document_id=%s error=%s",
                record.document_id,
                type(exc).__name__,
            )
        return None

    @staticmethod
    def _merge_compiled_chunks(
        existing: dict[UUID, ChunkEntry],
        affected: dict[UUID, ChunkEntry],
        compiled: list[ChunkEntry],
    ) -> None:
        """Carry canonical updates and duplicate removals through compensation steps."""
        for chunk in compiled:
            prior = affected.get(chunk.id)
            removed = chunk.metadata.get("wiki_merged_page_ids", [])
            old_removed = prior.metadata.get("wiki_merged_page_ids", []) if prior else []
            if not isinstance(removed, list) or not isinstance(old_removed, list):
                raise ValueError("invalid canonical deletion metadata")
            merged_ids = list(dict.fromkeys([*old_removed, *removed]))
            chunk.metadata["wiki_merged_page_ids"] = merged_ids
            for page_id in merged_ids:
                existing.pop(UUID(str(page_id)), None)
                affected.pop(UUID(str(page_id)), None)
            existing[chunk.id] = chunk
            affected[chunk.id] = chunk

    def _record_failure(
        self,
        record: IngestionRecord,
        worker_id: str,
        code: str,
        retryable: bool,
    ) -> None:
        if retryable and record.attempts < self.max_attempts:
            self.store.mark_retryable(record, worker_id=worker_id, code=code)
        else:
            self.store.mark_failed(record, worker_id=worker_id, code=code)
