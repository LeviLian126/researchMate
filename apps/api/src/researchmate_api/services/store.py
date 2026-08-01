"""Assemble the public in-memory repository from aggregate-focused store mixins."""

from researchmate_api.services._store_chunks import ChunkStoreMixin
from researchmate_api.services._store_conversations import ConversationStoreMixin
from researchmate_api.services._store_core import InMemoryStoreCore
from researchmate_api.services._store_documents import DocumentStoreMixin
from researchmate_api.services._store_limits import LimitStoreMixin
from researchmate_api.services._store_memory import MemoryStoreMixin
from researchmate_api.services._store_models import (
    ChunkEntry,
    IdempotencyDecision,
    UploadReservation,
)
from researchmate_api.services._store_projects import ProjectStoreMixin
from researchmate_api.services._store_protocol import ResearchMateRepository
from researchmate_api.services._store_runs import RunStoreMixin
from researchmate_api.services._store_text import chunk_text

__all__ = [
    "ChunkEntry",
    "IdempotencyDecision",
    "InMemoryResearchMateStore",
    "ResearchMateRepository",
    "UploadReservation",
    "chunk_text",
    "store",
]


class InMemoryResearchMateStore(
    ProjectStoreMixin,
    DocumentStoreMixin,
    RunStoreMixin,
    LimitStoreMixin,
    ChunkStoreMixin,
    ConversationStoreMixin,
    MemoryStoreMixin,
    InMemoryStoreCore,
):
    """Provide a thread-safe, process-local implementation of the repository protocol."""


store = InMemoryResearchMateStore()
