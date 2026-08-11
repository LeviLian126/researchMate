"""Verify the public upload format, extension, and MIME contract."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from researchmate_api.schemas.document import (
    EXTENSIONS_BY_TYPE,
    MIME_BY_TYPE,
    DocumentFileType,
    UploadUrlRequest,
)
from researchmate_worker.parsing import SUPPORTED_FILE_TYPES

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("filename", "file_type", "mime_type"),
    [
        ("notes.txt", "txt", "text/plain"),
        ("README.markdown", "md", "text/markdown"),
        (
            "evidence.xlsx",
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        ("events.ndjson", "jsonl", "application/x-ndjson"),
        ("analysis.ipynb", "ipynb", "application/x-ipynb+json"),
        ("service.py", "py", "text/x-python"),
    ],
)
def test_upload_request_accepts_supported_format_contracts(
    filename: str, file_type: DocumentFileType, mime_type: str
) -> None:
    """Accept representative structured and plain-text upload formats."""
    request = UploadUrlRequest(
        project_id=uuid4(),
        filename=filename,
        file_type=file_type,
        mime_type=mime_type,
        size_bytes=128,
    )

    assert request.file_type == file_type


def test_upload_request_rejects_extension_and_mime_disagreement() -> None:
    """Prevent declared metadata from routing disguised content to the wrong parser."""
    with pytest.raises(ValidationError, match="filename extension does not match"):
        UploadUrlRequest(
            project_id=uuid4(),
            filename="notes.pdf",
            file_type="md",
            mime_type="text/markdown",
            size_bytes=128,
        )

    with pytest.raises(ValidationError, match="mime_type"):
        UploadUrlRequest(
            project_id=uuid4(),
            filename="notes.md",
            file_type="md",
            mime_type="application/pdf",
            size_bytes=128,
        )


def test_api_worker_and_database_format_allowlists_stay_aligned() -> None:
    """Keep every accepted upload routable by the worker and durable schema."""
    api_types = set(MIME_BY_TYPE)
    migration = (
        ROOT / "infra/supabase/migrations/202608110008_expand_document_file_types.sql"
    ).read_text(encoding="utf-8")

    assert api_types == set(EXTENSIONS_BY_TYPE) == SUPPORTED_FILE_TYPES
    assert all(f"'{file_type}'" in migration for file_type in api_types)
