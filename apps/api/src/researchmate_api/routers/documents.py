from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from researchmate_api.dependencies import get_current_user, not_implemented_detail
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.document import (
    DocumentRecord,
    UploadCompleteRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)


router = APIRouter()


# 生成 R2 signed upload URL，具体签名由后续 storage agent 实现。
@router.post("/documents/upload-url", response_model=UploadUrlResponse)
def create_upload_url(
    _: UploadUrlRequest,
    user: CurrentUser = Depends(get_current_user),
) -> UploadUrlResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("UPLOAD_URL_NOT_IMPLEMENTED"),
    )


# 创建文档元数据，后续必须绑定 user_id 和 project_id。
@router.post("/documents", response_model=DocumentRecord, status_code=status.HTTP_201_CREATED)
def create_document(_: UploadUrlRequest, user: CurrentUser = Depends(get_current_user)) -> DocumentRecord:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("DOCUMENT_CREATE_NOT_IMPLEMENTED"),
    )


# 列出项目文档，后续必须按 user_id 和 project_id 过滤。
@router.get("/projects/{project_id}/documents", response_model=list[DocumentRecord])
def list_project_documents(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> list[DocumentRecord]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("DOCUMENT_LIST_NOT_IMPLEMENTED"),
    )


# 读取单个文档，后续必须校验资源归属。
@router.get("/documents/{document_id}", response_model=DocumentRecord)
def get_document(document_id: UUID, user: CurrentUser = Depends(get_current_user)) -> DocumentRecord:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("DOCUMENT_GET_NOT_IMPLEMENTED"),
    )


# 通知上传完成，后续必须创建 parse job。
@router.post("/documents/{document_id}/complete", status_code=status.HTTP_202_ACCEPTED)
def complete_upload(
    document_id: UUID,
    _: UploadCompleteRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("UPLOAD_COMPLETE_NOT_IMPLEMENTED"),
    )


# 删除文档，后续必须清理 metadata、R2 object、Qdrant points 和缓存。
@router.delete("/documents/{document_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_document(document_id: UUID, user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("DOCUMENT_DELETE_NOT_IMPLEMENTED"),
    )

