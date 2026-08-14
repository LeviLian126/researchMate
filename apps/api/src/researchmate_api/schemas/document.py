"""Define upload, document lifecycle, and response schemas for the document boundary."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from researchmate_api.schemas.common import (
    MAX_R2_OBJECT_KEY_LENGTH,
    MAX_UPLOAD_EXPIRES_IN_SECONDS,
    MAX_UPLOAD_FILENAME_LENGTH,
    MAX_UPLOAD_MIME_TYPE_LENGTH,
    MAX_UPLOAD_URL_LENGTH,
    MIN_R2_OBJECT_KEY_LENGTH,
    MIN_UPLOAD_EXPIRES_IN_SECONDS,
    MIN_UPLOAD_MIME_TYPE_LENGTH,
    MIN_UPLOAD_URL_LENGTH,
    DocumentStatus,
)

type DocumentFileType = Literal[
    "pdf",
    "docx",
    "pptx",
    "xlsx",
    "txt",
    "md",
    "csv",
    "tsv",
    "json",
    "jsonl",
    "xml",
    "html",
    "yaml",
    "toml",
    "rst",
    "log",
    "tex",
    "bib",
    "py",
    "ipynb",
    "js",
    "jsx",
    "ts",
    "tsx",
    "css",
    "scss",
    "sql",
    "sh",
    "ps1",
    "java",
    "c",
    "cpp",
    "h",
    "hpp",
    "cs",
    "go",
    "rs",
    "php",
    "rb",
    "swift",
    "kt",
    "kts",
]

MIME_BY_TYPE: dict[str, set[str]] = {
    "pdf": {"application/pdf"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "txt": {"text/plain"},
    "md": {"text/markdown", "text/plain", "text/x-markdown"},
    "csv": {"text/csv", "application/csv", "text/plain"},
    "tsv": {"text/tab-separated-values", "text/plain"},
    "json": {"application/json", "text/json", "text/plain"},
    "jsonl": {"application/x-ndjson", "application/jsonl", "text/plain"},
    "xml": {"application/xml", "text/xml", "text/plain"},
    "html": {"text/html", "application/xhtml+xml"},
    "yaml": {"application/yaml", "text/yaml", "application/x-yaml", "text/plain"},
    "toml": {"application/toml", "text/plain"},
    "rst": {"text/x-rst", "text/plain"},
    "log": {"text/plain"},
    "tex": {"text/x-tex", "application/x-tex", "text/plain"},
    "bib": {"text/x-bibtex", "text/plain"},
    "py": {"text/x-python", "text/plain"},
    "ipynb": {"application/x-ipynb+json", "application/json"},
    "js": {"text/javascript", "application/javascript", "text/plain"},
    "jsx": {"text/jsx", "text/javascript", "text/plain"},
    "ts": {"text/typescript", "application/typescript", "text/plain"},
    "tsx": {"text/tsx", "text/typescript", "text/plain"},
    "css": {"text/css", "text/plain"},
    "scss": {"text/x-scss", "text/plain"},
    "sql": {"application/sql", "text/x-sql", "text/plain"},
    "sh": {"application/x-sh", "text/x-shellscript", "text/plain"},
    "ps1": {"text/x-powershell", "text/plain"},
    "java": {"text/x-java-source", "text/plain"},
    "c": {"text/x-c", "text/plain"},
    "cpp": {"text/x-c++src", "text/plain"},
    "h": {"text/x-c", "text/plain"},
    "hpp": {"text/x-c++hdr", "text/plain"},
    "cs": {"text/x-csharp", "text/plain"},
    "go": {"text/x-go", "text/plain"},
    "rs": {"text/x-rust", "text/plain"},
    "php": {"application/x-httpd-php", "text/x-php", "text/plain"},
    "rb": {"application/x-ruby", "text/x-ruby", "text/plain"},
    "swift": {"text/x-swift", "text/plain"},
    "kt": {"text/x-kotlin", "text/plain"},
    "kts": {"text/x-kotlin", "text/plain"},
}
EXTENSIONS_BY_TYPE: dict[str, set[str]] = {
    file_type: {f".{file_type}"} for file_type in MIME_BY_TYPE
}
EXTENSIONS_BY_TYPE.update(
    {
        "txt": {".txt", ".text"},
        "md": {".md", ".markdown"},
        "jsonl": {".jsonl", ".ndjson"},
        "html": {".html", ".htm"},
        "yaml": {".yaml", ".yml"},
        "sh": {".sh", ".bash"},
        "cpp": {".cpp", ".cc", ".cxx"},
        "hpp": {".hpp", ".hh", ".hxx"},
    }
)
MAX_DOCUMENT_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_LOCAL_EXTRACTED_TEXT_CHARS = 1 * 1024 * 1024


def safe_upload_filename(filename: str) -> str:
    """Sanitize an uploaded filename for use inside a private object key."""
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return sanitized[:180] or "document"


# Define the request for obtaining an upload URL.
class UploadUrlRequest(BaseModel):
    """Validate metadata for a scoped direct-upload reservation."""

    project_id: UUID
    conversation_id: UUID | None = None
    filename: str = Field(min_length=1, max_length=MAX_UPLOAD_FILENAME_LENGTH)
    file_type: DocumentFileType
    mime_type: str = Field(
        min_length=MIN_UPLOAD_MIME_TYPE_LENGTH,
        max_length=MAX_UPLOAD_MIME_TYPE_LENGTH,
    )
    size_bytes: int = Field(gt=0, le=MAX_DOCUMENT_UPLOAD_BYTES)

    model_config = ConfigDict(extra="forbid")

    # Validate that MIME and extension types match to prevent disguised uploads.
    @model_validator(mode="after")
    def validate_mime_matches_type(self) -> UploadUrlRequest:
        if self.mime_type not in MIME_BY_TYPE[self.file_type]:
            raise ValueError(f"mime_type {self.mime_type} is not allowed for {self.file_type}")
        filename = self.filename.lower()
        if not any(
            filename.endswith(extension) for extension in EXTENSIONS_BY_TYPE[self.file_type]
        ):
            raise ValueError(f"filename extension does not match file_type {self.file_type}")
        return self


# Define the upload URL response.
class UploadUrlResponse(BaseModel):
    """Return a bounded direct-upload reservation and storage identity."""

    document_id: UUID
    upload_url: str = Field(
        min_length=MIN_UPLOAD_URL_LENGTH,
        max_length=MAX_UPLOAD_URL_LENGTH,
    )
    r2_object_key: str = Field(
        min_length=MIN_R2_OBJECT_KEY_LENGTH,
        max_length=MAX_R2_OBJECT_KEY_LENGTH,
    )
    expires_in_seconds: int = Field(
        ge=MIN_UPLOAD_EXPIRES_IN_SECONDS,
        le=MAX_UPLOAD_EXPIRES_IN_SECONDS,
    )


# Define the upload-complete notification.
class UploadCompleteRequest(BaseModel):
    """Accept production checksums and a bounded local-development text fallback."""

    checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    extracted_text: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_LOCAL_EXTRACTED_TEXT_CHARS,
    )

    model_config = ConfigDict(extra="forbid")


# Define the file metadata response.
class DocumentRecord(BaseModel):
    """Represent owner-scoped document metadata and lifecycle status."""

    id: UUID
    user_id: UUID
    project_id: UUID
    conversation_id: UUID | None = None
    filename: str
    file_type: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(use_enum_values=True)
