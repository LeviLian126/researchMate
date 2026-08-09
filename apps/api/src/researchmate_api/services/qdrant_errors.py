"""Normalize vector-store failures without exposing provider response details."""

from __future__ import annotations

import logging
from typing import NoReturn

LOGGER = logging.getLogger(__name__)


class VectorStoreRequestError(RuntimeError):
    """Carry the failed operation and whether a higher layer may retry it."""

    def __init__(self, operation: str, *, retryable: bool = True) -> None:
        super().__init__(f"Vector store {operation} failed")
        self.operation = operation
        self.retryable = retryable


def raise_vector_store_error(operation: str, exc: Exception) -> NoReturn:
    """Log a provider-safe failure summary and raise the typed boundary error."""
    LOGGER.warning("qdrant_%s_failed error=%s", operation, type(exc).__name__)
    raise VectorStoreRequestError(operation) from exc
