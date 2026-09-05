"""Expose the stable ingestion API while storage and orchestration evolve independently."""

from __future__ import annotations

from researchmate_worker.ingestion_models import (
    DocumentParser,
    IngestionEvent,
    IngestionFailure,
    IngestionRecord,
    IngestionStore,
    ObjectReader,
    PageProjection,
    ParsedBlock,
    ParserAdapterError,
    VectorProjection,
    WikiCompiler,
    WikiProjectState,
)
from researchmate_worker.ingestion_projections import build_projections
from researchmate_worker.ingestion_service import DocumentIngestionService
from researchmate_worker.ingestion_store import SqlIngestionStore

__all__ = [
    "DocumentIngestionService",
    "DocumentParser",
    "IngestionEvent",
    "IngestionFailure",
    "IngestionRecord",
    "IngestionStore",
    "ObjectReader",
    "PageProjection",
    "ParsedBlock",
    "ParserAdapterError",
    "SqlIngestionStore",
    "VectorProjection",
    "WikiCompiler",
    "WikiProjectState",
    "build_projections",
]
