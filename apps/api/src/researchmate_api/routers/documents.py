"""Expose owner-scoped document upload, lookup, ingestion, and deletion routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from researchmate_api.dependencies import get_current_user, get_store, raise_api_error
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.document import (
    DocumentRecord,
    UploadCompleteRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)
from researchmate_api.services.object_storage import (
    ObjectStorageConfigurationError,
    ObjectStorageRequestError,
    UploadVerificationError,
)
from researchmate_api.services.store import ResearchMateRepository

router = APIRouter()


# Generate a local R2 signed upload URL placeholder and create an uploaded document record.
@router.post("/documents/upload-url", response_model=UploadUrlResponse)
def create_upload_url(
    payload: UploadUrlRequest,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> UploadUrlResponse:
    """Reserve document metadata and return a signed object-upload request."""
    response = repository.create_upload_url(user, payload)
    if response is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return response


# Create or confirm document metadata; must bind user_id and project_id.
@router.post("/documents", response_model=DocumentRecord, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: UploadUrlRequest,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> DocumentRecord:
    """Create owner-scoped document metadata for an active project."""
    document = repository.create_document(user, payload)
    if document is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return document


# List project documents, filtered by user_id and project_id.
@router.get("/projects/{project_id}/documents", response_model=list[DocumentRecord])
def list_project_documents(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> list[DocumentRecord]:
    """List documents visible through the caller-owned project."""
    documents = repository.list_project_documents(user, project_id)
    if documents is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return documents


@router.get("/conversations/{conversation_id}/documents", response_model=list[DocumentRecord])
def list_conversation_documents(
    conversation_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> list[DocumentRecord]:
    """List documents attached to a caller-owned conversation."""
    documents = repository.list_conversation_documents(user, conversation_id)
    if documents is None:
        raise_api_error(
            status.HTTP_404_NOT_FOUND,
            "CONVERSATION_NOT_FOUND",
            "Conversation was not found.",
        )
    return documents


# Read a single document; must validate resource ownership.
@router.get("/documents/{document_id}", response_model=DocumentRecord)
def get_document(
    document_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> DocumentRecord:
    """Return one document only when it belongs to the caller."""
    document = repository.get_document(user, document_id)
    if document is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Document was not found.")
    return document


# Notify upload completion; local development may pass extracted_text, production worker should parse from R2.
@router.post("/documents/{document_id}/complete", status_code=status.HTTP_202_ACCEPTED)
def complete_upload(
    document_id: UUID,
    payload: UploadCompleteRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> dict[str, str]:
    """Verify an upload and enqueue its asynchronous ingestion job."""
    extracted_text = payload.extracted_text if payload else None
    checksum_sha256 = payload.checksum_sha256 if payload else None
    try:
        job = repository.complete_document(user, document_id, extracted_text, checksum_sha256)
    except UploadVerificationError as exc:
        raise_api_error(status.HTTP_409_CONFLICT, exc.code, str(exc))
    except ObjectStorageRequestError as exc:
        raise_api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "OBJECT_STORAGE_UNAVAILABLE",
            "The uploaded object could not be verified. Retry later."
            if exc.retryable
            else "The uploaded object could not be verified.",
        )
    except ObjectStorageConfigurationError:
        raise_api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "OBJECT_STORAGE_NOT_CONFIGURED",
            "Object storage is not configured for asynchronous ingestion.",
        )
    if job is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Document was not found.")
    return {"job_id": str(job.id), "status": job.status}


# Delete a document and clean up metadata, chunks, and local cache.
@router.delete("/documents/{document_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_document(
    document_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> dict[str, str]:
    """Enqueue deletion of an owner-scoped document and its projections."""
    job = repository.delete_document(user, document_id)
    if job is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Document was not found.")
    return {"job_id": str(job.id), "status": job.status}
