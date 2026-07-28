from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# 定义任务类型，Task 只控制执行目标。
class TaskType(str, Enum):
    ANSWER = "answer"
    QUIZ = "quiz"


# 定义文件状态，后续 worker 只允许沿此状态机推进。
class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"
    DELETED = "deleted"


# 定义异步任务状态。
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# 定义引用来源类型。
class SourceType(str, Enum):
    LOCAL_DOC = "local_doc"
    WEB_PAGE = "web_page"


# 定义题目难度。
class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# 定义统一错误体。
class ErrorDetail(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    message: str = Field(min_length=1, max_length=300)
    request_id: str = Field(min_length=4, max_length=120)


# 定义统一错误响应。
class ErrorResponse(BaseModel):
    error: ErrorDetail


# 定义当前认证用户。
class CurrentUser(BaseModel):
    id: UUID
    email: str | None = Field(default=None, max_length=320)
    role: Literal["user", "developer", "admin"] = "user"


# 定义回答顶部来源统计。
class SourceSummary(BaseModel):
    local_chunks: int = Field(default=0, ge=0, le=50)
    web_pages: int = Field(default=0, ge=0, le=20)


# 定义回答和测验共用引用结构。
class Citation(BaseModel):
    id: UUID
    source_type: SourceType
    document_id: UUID | None = None
    chunk_id: UUID | None = None
    page_no: int | None = Field(default=None, ge=1)
    slide_no: int | None = Field(default=None, ge=1)
    url: str | None = Field(default=None, max_length=2048)
    quote: str = Field(min_length=1, max_length=1200)
    claim_id: str | None = Field(default=None, max_length=120)

    model_config = ConfigDict(use_enum_values=True)


# 定义统一聊天入口在服务端解析出的执行计划。
class ExecutionPlan(BaseModel):
    task_type: TaskType
    allowed_tools: list[str] = Field(min_length=1, max_length=12)
    requires_local_docs: bool
    requires_web: bool
    context_strategy: Literal[
        "chat",
        "full_context",
        "hybrid_retrieval",
        "web",
        "hybrid_retrieval_web",
        "quiz",
    ]
    output_schema: Literal["ChatAnswer", "GroundedAnswer", "QuizSet"]

    model_config = ConfigDict(use_enum_values=True)
