from enum import Enum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, Field


# 定义 worker 支持的任务类型。
class WorkerJobType(str, Enum):
    PARSE_DOCUMENT = "parse_document"
    INDEX_DOCUMENT = "index_document"
    READ_WEB_PAGE = "read_web_page"
    RUN_RAG_EVAL = "run_rag_eval"
    DELETE_PROJECT = "delete_project"


# 定义 worker 任务负载。
class WorkerJobPayload(BaseModel):
    job_id: UUID
    user_id: UUID
    project_id: UUID | None = None
    document_id: UUID | None = None
    type: WorkerJobType
    metadata: dict = Field(default_factory=dict)


# 定义 worker handler 抽象。
class WorkerJobHandler(Protocol):
    # 处理已经校验过的 worker 任务。
    def handle(self, payload: WorkerJobPayload) -> None:
        """Process a validated worker job payload."""
