"""Expose the stable deletion API while implementations remain split by aggregate."""

from __future__ import annotations

from researchmate_worker.deletion_document import DocumentDeletionService, SqlDeletionStore
from researchmate_worker.deletion_models import (
    DeletionRecord,
    DeletionStore,
    DocumentDeletionEvent,
    ObjectDeletion,
    ProjectDeletionEvent,
    ProjectDeletionRecord,
    ProjectDeletionStore,
    VectorDeletion,
)
from researchmate_worker.deletion_project import ProjectDeletionService, SqlProjectDeletionStore

__all__ = [
    "DeletionRecord",
    "DeletionStore",
    "DocumentDeletionEvent",
    "DocumentDeletionService",
    "ObjectDeletion",
    "ProjectDeletionEvent",
    "ProjectDeletionRecord",
    "ProjectDeletionService",
    "ProjectDeletionStore",
    "SqlDeletionStore",
    "SqlProjectDeletionStore",
    "VectorDeletion",
]
