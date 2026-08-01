"""Coordinate object download, parsing, projection, indexing, and terminal job state."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from researchmate_api.services.object_storage import ObjectStorageRequestError
from researchmate_api.services.qdrant_store import VectorStoreRequestError

from researchmate_worker.ingestion_models import (
    DocumentParser,
    IngestionEvent,
    IngestionFailure,
    IngestionRecord,
    IngestionStore,
    ObjectReader,
    ParserAdapterError,
    VectorProjection,
)
from researchmate_worker.ingestion_projections import build_projections


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
    ) -> None:
        self.store = store
        self.object_reader = object_reader
        self.parser = parser
        self.vector_projection = vector_projection
        self.pipeline_version = pipeline_version
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.max_upload_bytes = max_upload_bytes

    def handle(self, event: IngestionEvent, *, worker_id: str) -> str:
        """Execute one claimed ingestion delivery and persist a safe terminal outcome."""
        record = self.store.claim(event, worker_id=worker_id, lease_seconds=self.lease_seconds)
        if record is None:
            return "not_claimed"
        try:
            with TemporaryDirectory(prefix="researchmate-ingest-") as directory:
                source = Path(directory) / f"source.{record.file_type}"
                self.object_reader.download_to_file(record.r2_object_key, source)
                if source.stat().st_size > self.max_upload_bytes:
                    raise IngestionFailure("DOCUMENT_TOO_LARGE", retryable=False)
                actual_checksum = sha256(source.read_bytes()).hexdigest()
                if record.checksum_sha256 and actual_checksum != record.checksum_sha256:
                    raise IngestionFailure("CHECKSUM_MISMATCH", retryable=False)
                blocks = self.parser.parse(source, file_type=record.file_type)
            pages, chunks = build_projections(
                record,
                blocks,
                pipeline_version=self.pipeline_version,
            )
            if not pages or not chunks:
                raise IngestionFailure("NO_EXTRACTABLE_TEXT", retryable=False)
            self.store.replace_content(
                record,
                worker_id=worker_id,
                pages=pages,
                chunks=chunks,
                pipeline_version=self.pipeline_version,
            )
            self.vector_projection.upsert_chunks(chunks, pipeline_version=self.pipeline_version)
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
        except Exception as exc:
            self._record_failure(record, worker_id, "INGESTION_INTERNAL_ERROR", False)
            raise IngestionFailure("INGESTION_INTERNAL_ERROR", retryable=False) from exc

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
