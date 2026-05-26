from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import UUID, uuid4

from researchmate_api.schemas.ask import AskResponse
from researchmate_api.schemas.common import (
    Citation,
    CurrentUser,
    DocumentStatus,
    ExecutionPlan,
    JobStatus,
    SourceSummary,
    SourceType,
)
from researchmate_api.schemas.document import DocumentRecord, UploadUrlRequest, UploadUrlResponse
from researchmate_api.schemas.job import JobRecord
from researchmate_api.schemas.project import ProjectCreate, ProjectRecord
from researchmate_api.schemas.quiz import QuizSet
from researchmate_api.schemas.sources import RunSourcesResponse
from researchmate_api.schemas.trace import DeveloperTrace, ToolCallTrace


@dataclass
class ChunkEntry:
    id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID | None
    source_type: SourceType
    source_title: str
    text: str
    page_no: int | None = None
    slide_no: int | None = None
    url: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class UploadReservation:
    document_id: UUID
    r2_object_key: str
    request: UploadUrlRequest
    created_at: datetime


# 线程安全的本地开发仓库，生产环境可替换为 Supabase/R2/Qdrant/Redis adapter。
class InMemoryResearchMateStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self.reset()

    # 清空本地状态，主要供测试使用。
    def reset(self) -> None:
        with self._lock:
            self.profiles: dict[UUID, CurrentUser] = {}
            self.projects: dict[UUID, ProjectRecord] = {}
            self.documents: dict[UUID, DocumentRecord] = {}
            self.jobs: dict[UUID, JobRecord] = {}
            self.uploads: dict[UUID, UploadReservation] = {}
            self.chunks: dict[UUID, ChunkEntry] = {}
            self.run_sources: dict[UUID, RunSourcesResponse] = {}
            self.ask_responses: dict[UUID, AskResponse] = {}
            self.traces: dict[UUID, DeveloperTrace] = {}
            self.quiz_sets: dict[UUID, QuizSet] = {}
            self.project_quiz_sets: dict[UUID, list[UUID]] = {}
            self.api_usage: dict[tuple[UUID, str, str], int] = {}

    # 确保 profile 存在。
    def ensure_user(self, user: CurrentUser) -> CurrentUser:
        with self._lock:
            self.profiles[user.id] = user
            return user

    # 创建项目。
    def create_project(self, user: CurrentUser, payload: ProjectCreate) -> ProjectRecord:
        with self._lock:
            self.ensure_user(user)
            now = datetime.now(UTC)
            project = ProjectRecord(
                id=uuid4(),
                user_id=user.id,
                name=payload.name,
                status="active",
                expires_at=now + timedelta(days=7),
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
            self.projects[project.id] = project
            return project

    # 列出当前用户项目。
    def list_projects(self, user: CurrentUser) -> list[ProjectRecord]:
        with self._lock:
            return [
                project
                for project in self.projects.values()
                if project.user_id == user.id and project.deleted_at is None
            ]

    # 读取用户可见项目。
    def get_project(self, user: CurrentUser, project_id: UUID) -> ProjectRecord | None:
        with self._lock:
            project = self.projects.get(project_id)
            if project is None or project.user_id != user.id or project.deleted_at is not None:
                return None
            return project

    # 删除项目并同步清理本地开发存储中的关联数据。
    def delete_project(self, user: CurrentUser, project_id: UUID) -> JobRecord | None:
        with self._lock:
            project = self.get_project(user, project_id)
            if project is None:
                return None
            now = datetime.now(UTC)
            self.projects[project_id] = project.model_copy(
                update={"status": "deleted", "deleted_at": now, "updated_at": now}
            )
            for document in list(self.documents.values()):
                if document.project_id == project_id and document.user_id == user.id:
                    self.documents[document.id] = document.model_copy(
                        update={"status": DocumentStatus.DELETED, "deleted_at": now, "updated_at": now}
                    )
            for chunk_id, chunk in list(self.chunks.items()):
                if chunk.project_id == project_id and chunk.user_id == user.id:
                    del self.chunks[chunk_id]
            job = self._create_job_locked(
                user=user,
                project_id=project_id,
                document_id=None,
                job_type="delete_project",
                status=JobStatus.SUCCEEDED,
                progress=100,
            )
            return job

    # 生成本地 signed URL 占位并创建 uploaded 文档记录。
    def create_upload_url(self, user: CurrentUser, payload: UploadUrlRequest) -> UploadUrlResponse | None:
        with self._lock:
            if self.get_project(user, payload.project_id) is None:
                return None
            now = datetime.now(UTC)
            document_id = uuid4()
            r2_object_key = f"users/{user.id}/projects/{payload.project_id}/documents/{document_id}/{payload.filename}"
            document = DocumentRecord(
                id=document_id,
                user_id=user.id,
                project_id=payload.project_id,
                filename=payload.filename,
                file_type=payload.file_type,
                mime_type=payload.mime_type,
                size_bytes=payload.size_bytes,
                status=DocumentStatus.UPLOADED,
                error_message=None,
                expires_at=now + timedelta(days=7),
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
            self.documents[document_id] = document
            self.uploads[document_id] = UploadReservation(document_id, r2_object_key, payload, now)
            return UploadUrlResponse(
                document_id=document_id,
                upload_url=f"http://localhost:8000/api/v1/dev/upload/{document_id}",
                r2_object_key=r2_object_key,
                expires_in_seconds=600,
            )

    # 创建或复用文档元数据。
    def create_document(self, user: CurrentUser, payload: UploadUrlRequest) -> DocumentRecord | None:
        with self._lock:
            if self.get_project(user, payload.project_id) is None:
                return None
            for reservation in self.uploads.values():
                if (
                    reservation.request.project_id == payload.project_id
                    and reservation.request.filename == payload.filename
                    and reservation.request.size_bytes == payload.size_bytes
                ):
                    document = self.documents.get(reservation.document_id)
                    if document and document.user_id == user.id:
                        return document
            response = self.create_upload_url(user, payload)
            return None if response is None else self.documents[response.document_id]

    # 列出项目文件。
    def list_project_documents(self, user: CurrentUser, project_id: UUID) -> list[DocumentRecord] | None:
        with self._lock:
            if self.get_project(user, project_id) is None:
                return None
            return [
                document
                for document in self.documents.values()
                if document.project_id == project_id
                and document.user_id == user.id
                and document.deleted_at is None
            ]

    # 读取用户可见文件。
    def get_document(self, user: CurrentUser, document_id: UUID) -> DocumentRecord | None:
        with self._lock:
            document = self.documents.get(document_id)
            if document is None or document.user_id != user.id or document.deleted_at is not None:
                return None
            return document

    # 完成上传并写入解析后的本地 chunks。
    def complete_document(self, user: CurrentUser, document_id: UUID, extracted_text: str | None) -> JobRecord | None:
        with self._lock:
            document = self.get_document(user, document_id)
            if document is None:
                return None
            now = datetime.now(UTC)
            status = DocumentStatus.READY if extracted_text and extracted_text.strip() else DocumentStatus.FAILED
            error_message = None if status == DocumentStatus.READY else "No extractable text was provided."
            self.documents[document_id] = document.model_copy(
                update={"status": status, "error_message": error_message, "updated_at": now}
            )
            for chunk_id, chunk in list(self.chunks.items()):
                if chunk.document_id == document_id:
                    del self.chunks[chunk_id]
            if extracted_text and extracted_text.strip():
                for index, text in enumerate(chunk_text(extracted_text), start=1):
                    chunk_id = uuid4()
                    self.chunks[chunk_id] = ChunkEntry(
                        id=chunk_id,
                        user_id=user.id,
                        project_id=document.project_id,
                        document_id=document.id,
                        source_type=SourceType.LOCAL_DOC,
                        source_title=document.filename,
                        text=text,
                        page_no=index,
                    )
            return self._create_job_locked(
                user=user,
                project_id=document.project_id,
                document_id=document.id,
                job_type="parse_and_index_document",
                status=JobStatus.SUCCEEDED if status == DocumentStatus.READY else JobStatus.FAILED,
                progress=100,
                error_message=error_message,
            )

    # 删除单个文档。
    def delete_document(self, user: CurrentUser, document_id: UUID) -> JobRecord | None:
        with self._lock:
            document = self.get_document(user, document_id)
            if document is None:
                return None
            now = datetime.now(UTC)
            self.documents[document_id] = document.model_copy(
                update={"status": DocumentStatus.DELETED, "deleted_at": now, "updated_at": now}
            )
            for chunk_id, chunk in list(self.chunks.items()):
                if chunk.document_id == document_id:
                    del self.chunks[chunk_id]
            return self._create_job_locked(
                user=user,
                project_id=document.project_id,
                document_id=document.id,
                job_type="delete_document",
                status=JobStatus.SUCCEEDED,
                progress=100,
            )

    # 查询 job。
    def get_job(self, user: CurrentUser, job_id: UUID) -> JobRecord | None:
        with self._lock:
            job = self.jobs.get(job_id)
            if job is None or job.user_id != user.id:
                return None
            return job

    # 按 run_id 读取 Sources panel。
    def get_run_sources(self, user: CurrentUser, run_id: UUID) -> RunSourcesResponse | None:
        with self._lock:
            response = self.run_sources.get(run_id)
            ask_response = self.ask_responses.get(run_id)
            if response is None or ask_response is None:
                return None
            trace = self.traces.get(ask_response.trace_id)
            if trace is None or trace.user_id != user.id:
                return None
            return response

    # 读取管理员 trace。
    def get_trace(self, trace_id: UUID) -> DeveloperTrace | None:
        with self._lock:
            return self.traces.get(trace_id)

    # 记录一次 Ask/Quiz 运行。
    def record_run(
        self,
        user: CurrentUser,
        project_id: UUID,
        plan: ExecutionPlan,
        router_reason: str,
        retrieved_chunks: list[ChunkEntry],
        citations: list[Citation],
        tool_calls: list[ToolCallTrace],
        validation_result: dict,
    ) -> tuple[UUID, UUID]:
        with self._lock:
            run_id = uuid4()
            trace_id = uuid4()
            summary = SourceSummary(
                local_chunks=sum(1 for citation in citations if citation.source_type == SourceType.LOCAL_DOC),
                web_pages=sum(1 for citation in citations if citation.source_type == SourceType.WEB_PAGE),
            )
            self.run_sources[run_id] = RunSourcesResponse(
                run_id=run_id,
                summary=summary,
                citations=citations,
            )
            self.traces[trace_id] = DeveloperTrace(
                trace_id=trace_id,
                user_id=user.id,
                project_id=project_id,
                run_id=run_id,
                execution_plan=plan,
                router_reason=router_reason,
                retrieved_chunks=[
                    {
                        "chunk_id": str(chunk.id),
                        "document_id": str(chunk.document_id) if chunk.document_id else None,
                        "source_title": chunk.source_title,
                        "page_no": chunk.page_no,
                        "score_context": chunk.text[:240],
                    }
                    for chunk in retrieved_chunks
                ],
                tool_calls=tool_calls,
                validation_result=validation_result,
                latency_ms=0,
                token_usage=None,
                errors=[] if validation_result.get("passed", True) else ["validation_failed"],
                created_at=datetime.now(UTC),
            )
            return run_id, trace_id

    # 保存 Ask 响应。
    def save_ask_response(self, response: AskResponse) -> AskResponse:
        with self._lock:
            self.ask_responses[response.run_id] = response
            return response

    # 保存 QuizSet 并建立 project 索引。
    def save_quiz_set(self, project_id: UUID, quiz_set: QuizSet) -> QuizSet:
        with self._lock:
            self.quiz_sets[quiz_set.id] = quiz_set
            self.project_quiz_sets.setdefault(project_id, []).insert(0, quiz_set.id)
            return quiz_set

    # 列出项目 Quiz 历史。
    def list_quiz_sets(self, user: CurrentUser, project_id: UUID) -> list[QuizSet] | None:
        with self._lock:
            if self.get_project(user, project_id) is None:
                return None
            ids = self.project_quiz_sets.get(project_id, [])
            return [self.quiz_sets[quiz_id] for quiz_id in ids if quiz_id in self.quiz_sets]

    # 对用户每日 API 调用做轻量限流。
    def increment_usage(self, user: CurrentUser, kind: str, limit: int) -> bool:
        with self._lock:
            today = datetime.now(UTC).date().isoformat()
            key = (user.id, today, kind)
            current = self.api_usage.get(key, 0) + 1
            self.api_usage[key] = current
            return current <= limit

    # 读取用户项目内的 ready chunks。
    def project_chunks(self, user: CurrentUser, project_id: UUID) -> list[ChunkEntry] | None:
        with self._lock:
            if self.get_project(user, project_id) is None:
                return None
            return [
                chunk
                for chunk in self.chunks.values()
                if chunk.user_id == user.id and chunk.project_id == project_id
            ]

    # 创建 job 记录，调用方需已持锁。
    def _create_job_locked(
        self,
        user: CurrentUser,
        project_id: UUID | None,
        document_id: UUID | None,
        job_type: str,
        status: JobStatus,
        progress: int,
        error_message: str | None = None,
    ) -> JobRecord:
        now = datetime.now(UTC)
        job = JobRecord(
            id=uuid4(),
            user_id=user.id,
            project_id=project_id,
            document_id=document_id,
            type=job_type,
            status=status,
            progress=progress,
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )
        self.jobs[job.id] = job
        return job


# 将长文本拆成可追溯的 chunk。
def chunk_text(text: str, target_size: int = 900) -> list[str]:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []
    paragraphs = normalized.split("\n")
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= target_size:
            current = f"{current}\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
            while len(current) > target_size:
                chunks.append(current[:target_size].strip())
                current = current[target_size:].strip()
    if current:
        chunks.append(current)
    return chunks


store = InMemoryResearchMateStore()
