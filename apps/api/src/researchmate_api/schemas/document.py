"""Define upload, document lifecycle, and response schemas for the document boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from researchmate_api.schemas.common import DocumentStatus

MIME_BY_TYPE = {
    "pdf": {"application/pdf"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
}


# Define the request for obtaining an upload URL.
class UploadUrlRequest(BaseModel):
    """Validate metadata for a scoped direct-upload reservation."""

    project_id: UUID
    conversation_id: UUID | None = None
    filename: str = Field(min_length=1, max_length=240)
    file_type: Literal["pdf", "docx", "pptx"]
    mime_type: str = Field(min_length=3, max_length=120)
    size_bytes: int = Field(gt=0, le=25 * 1024 * 1024)

    model_config = ConfigDict(extra="forbid")

    # Validate that MIME and extension types match to prevent disguised uploads.
    @model_validator(mode="after")
    def validate_mime_matches_type(self) -> UploadUrlRequest:
        if self.mime_type not in MIME_BY_TYPE[self.file_type]:
            raise ValueError(f"mime_type {self.mime_type} is not allowed for {self.file_type}")
        return self


# Define the upload URL response.
class UploadUrlResponse(BaseModel):
    """Return a bounded direct-upload reservation and storage identity."""

    document_id: UUID
    upload_url: str = Field(min_length=1, max_length=4096)
    r2_object_key: str = Field(min_length=16, max_length=512)
    expires_in_seconds: int = Field(ge=60, le=900)


# Define the upload-complete notification.
class UploadCompleteRequest(BaseModel):
    """Accept the upload checksum and the explicitly local-only extraction fallback."""

    checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    extracted_text: str | None = Field(
        default=None,
        max_length=200_000,
        description="Local development fallback. Production worker should extract text from R2.",
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
