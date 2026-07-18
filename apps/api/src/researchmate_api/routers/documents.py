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
from researchmate_api.services.store import ResearchMateRepository
from researchmate_api.services.object_storage import (
    ObjectStorageConfigurationError,
    ObjectStorageRequestError,
    UploadVerificationError,
)


router = APIRouter()


# 生成本地 R2 signed upload URL 占位，并创建 uploaded 文档记录。
@router.post("/documents/upload-url", response_model=UploadUrlResponse)
def create_upload_url(
    payload: UploadUrlRequest,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> UploadUrlResponse:
    response = repository.create_upload_url(user, payload)
    if response is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return response


# 创建或确认文档元数据，必须绑定 user_id 和 project_id。
@router.post("/documents", response_model=DocumentRecord, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: UploadUrlRequest,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> DocumentRecord:
    document = repository.create_document(user, payload)
    if document is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return document


# 列出项目文档，按 user_id 和 project_id 过滤。
@router.get("/projects/{project_id}/documents", response_model=list[DocumentRecord])
def list_project_documents(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> list[DocumentRecord]:
    documents = repository.list_project_documents(user, project_id)
    if documents is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return documents


# 读取单个文档，必须校验资源归属。
@router.get("/documents/{document_id}", response_model=DocumentRecord)
def get_document(
    document_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> DocumentRecord:
    document = repository.get_document(user, document_id)
    if document is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Document was not found.")
    return document


# 通知上传完成；本地开发可传 extracted_text，生产 worker 应从 R2 解析。
@router.post("/documents/{document_id}/complete", status_code=status.HTTP_202_ACCEPTED)
def complete_upload(
    document_id: UUID,
    payload: UploadCompleteRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> dict[str, str]:
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


# 删除文档并清理 metadata、chunks 和本地缓存。
@router.delete("/documents/{document_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_document(
    document_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> dict[str, str]:
    job = repository.delete_document(user, document_id)
    if job is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Document was not found.")
    return {"job_id": str(job.id), "status": job.status}
