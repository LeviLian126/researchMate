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


# 定义获取上传地址的请求。
class UploadUrlRequest(BaseModel):
    project_id: UUID
    filename: str = Field(min_length=1, max_length=240)
    file_type: Literal["pdf", "docx", "pptx"]
    mime_type: str = Field(min_length=3, max_length=120)
    size_bytes: int = Field(gt=0, le=25 * 1024 * 1024)

    # 校验 MIME 与扩展类型一致，避免伪装上传。
    @model_validator(mode="after")
    def validate_mime_matches_type(self) -> "UploadUrlRequest":
        if self.mime_type not in MIME_BY_TYPE[self.file_type]:
            raise ValueError(f"mime_type {self.mime_type} is not allowed for {self.file_type}")
        return self


# 定义上传地址响应。
class UploadUrlResponse(BaseModel):
    document_id: UUID
    upload_url: str = Field(min_length=1, max_length=4096)
    r2_object_key: str = Field(min_length=16, max_length=512)
    expires_in_seconds: int = Field(ge=60, le=900)


# 定义上传完成通知。
class UploadCompleteRequest(BaseModel):
    checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    extracted_text: str | None = Field(
        default=None,
        max_length=200_000,
        description="Local development fallback. Production worker should extract text from R2.",
    )


# 定义文件元数据响应。
class DocumentRecord(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID
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
