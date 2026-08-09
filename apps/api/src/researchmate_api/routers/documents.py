"""Expose owner-scoped document upload, lookup, ingestion, and deletion routes."""

from __future__ import annotations

from tempfile import SpooledTemporaryFile
from typing import Annotated
from uuid import UUID

from anyio import to_thread
from fastapi import APIRouter, Depends, Header, Request, Response, status

from researchmate_api.dependencies import (
    get_current_user,
    get_object_storage,
    get_store,
    raise_api_error,
)
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.document import (
    MAX_DOCUMENT_UPLOAD_BYTES,
    DocumentRecord,
    UploadCompleteRequest,
    UploadUrlRequest,
    UploadUrlResponse,
    safe_upload_filename,
)
from researchmate_api.services.object_storage import (
    ObjectStorageConfigurationError,
    ObjectStorageRequestError,
    S3CompatibleObjectStorage,
    UploadVerificationError,
)
from researchmate_api.services.store import ResearchMateRepository

router = APIRouter()


@router.put("/documents/{document_id}/content", status_code=status.HTTP_204_NO_CONTENT)
async def upload_document_content(
    document_id: UUID,
    request: Request,
    content_type: Annotated[str | None, Header()] = None,
    content_length: Annotated[int | None, Header()] = None,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
    object_storage: S3CompatibleObjectStorage | None = Depends(get_object_storage),
) -> Response:
    """Proxy a bounded owner-scoped upload when provider CORS is unavailable."""
    document = repository.get_document(user, document_id)
    if document is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Document was not found.")
    if object_storage is None:
        raise_api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "OBJECT_STORAGE_NOT_CONFIGURED",
            "Object storage is not configured for uploads.",
        )
    if content_type != document.mime_type:
        raise_api_error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "MIME_MISMATCH",
            "Upload content type does not match the reserved document.",
        )
    if content_length is not None and content_length != document.size_bytes:
        raise_api_error(
            status.HTTP_409_CONFLICT,
            "SIZE_MISMATCH",
            "Upload size does not match the reserved document.",
        )

    received = 0
    with SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b") as source:
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_DOCUMENT_UPLOAD_BYTES or received > document.size_bytes:
                raise_api_error(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    "UPLOAD_TOO_LARGE",
                    "Upload exceeds the reserved document size.",
                )
            source.write(chunk)
        if received != document.size_bytes:
            raise_api_error(
                status.HTTP_409_CONFLICT,
                "SIZE_MISMATCH",
                "Upload size does not match the reserved document.",
            )
        source.seek(0)
        object_key = (
            f"users/{user.id}/projects/{document.project_id}/documents/{document.id}/"
            f"{safe_upload_filename(document.filename)}"
        )
        try:
            await to_thread.run_sync(
                lambda: object_storage.upload_stream(
                    object_key, source, content_type=document.mime_type
                )
            )
        except ObjectStorageRequestError as exc:
            raise_api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "OBJECT_STORAGE_UNAVAILABLE",
                "The object storage upload failed. Retry later."
                if exc.retryable
                else "The object storage upload failed.",
            )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
