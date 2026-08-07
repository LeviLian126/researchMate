"""Own Quiz retrieval, generation, coverage, usage, trace, and persistence orchestration."""

from __future__ import annotations

from time import monotonic
from uuid import uuid4

from researchmate_api.schemas.common import CurrentUser, ExecutionPlan, TaskType
from researchmate_api.schemas.quiz import QuizCoverage, QuizRequest, QuizResponse
from researchmate_api.schemas.trace import ToolCallTrace
from researchmate_api.services.answering import build_grounded_answer
from researchmate_api.services.llm import ChatProvider, ProviderRequestError
from researchmate_api.services.quiz_generation import (
    QuizGenerationError,
    generate_llm_quiz_set,
    generate_quiz_set,
)
from researchmate_api.services.retrieval import retrieve_local_chunks
from researchmate_api.services.store import ChunkEntry, ResearchMateRepository


class QuizServiceError(RuntimeError):
    """Carry a stable Quiz failure across interface adapters."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        """Record the public error code, safe message, and status."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class QuizService:
    """Generate one source-backed Quiz without treating instructions as a search query."""

    def __init__(
        self,
        repository: ResearchMateRepository,
        chat_provider: ChatProvider | None,
    ) -> None:
        """Bind the persistence and optional provider boundaries."""
        self.repository = repository
        self.chat_provider = chat_provider

    def create(self, user: CurrentUser, payload: QuizRequest) -> QuizResponse:
        """Validate scope, select evidence, generate, measure, and persist one Quiz."""
        project = self.repository.get_project(user, payload.project_id)
        if project is None or project.status != "active":
            self._error("PROJECT_NOT_FOUND", "Project was not found.", 404)
        if project.kind != "workspace":
            self._error("QUIZ_NOT_AVAILABLE", "Quiz is available only inside a project.", 404)
        chunks = self.repository.project_chunks(user, payload.project_id)
        if chunks is None:
            self._error("PROJECT_NOT_FOUND", "Project was not found.", 404)
        selection_started = monotonic()
        retrieved, coverage = self._select_chunks(chunks, payload)
        selection_latency = round((monotonic() - selection_started) * 1000)
        if not retrieved:
            self._error(
                "DOCUMENT_NOT_INDEXED",
                "No ready local document chunks exist for quiz generation.",
                409,
            )
        _, citations, _ = build_grounded_answer(payload.prompt, retrieved)
        generation_started = monotonic()
        try:
            if self.chat_provider is not None:
                quiz_set, _ = generate_llm_quiz_set(
                    self.chat_provider,
                    retrieved,
                    citations,
                    payload.prompt,
                    payload.single_choice_count,
                    payload.fill_blank_count,
                    payload.subjective_count,
                )
            else:
                quiz_set = generate_quiz_set(
                    retrieved,
                    citations,
                    payload.single_choice_count,
                    payload.fill_blank_count,
                    payload.subjective_count,
                )
        except (ProviderRequestError, QuizGenerationError) as exc:
            raise QuizServiceError(
                "QUIZ_PROVIDER_UNAVAILABLE",
                "The quiz provider could not produce a validated source-backed quiz.",
                503,
            ) from exc
        # Quota counts successful generation only; provider failures do not consume quota.
        if not self.repository.increment_usage(user, "quiz", limit=100):
            self._error("RATE_LIMITED", "Daily quiz quota exceeded.", 429)
        generation_latency = round((monotonic() - generation_started) * 1000)
        validation_result = {
            "passed": bool(quiz_set.questions),
            "question_count": len(quiz_set.questions),
            "coverage": coverage.model_dump(),
        }
        run_id, trace_id = self.repository.record_quiz_run(
            user=user,
            project_id=payload.project_id,
            message=payload.prompt,
            plan=self._plan(),
            router_reason="Quiz uses an explicit resource scope and local evidence.",
            retrieved_chunks=retrieved,
            citations=citations,
            tool_calls=self._tool_calls(
                payload,
                coverage,
                selection_latency,
                generation_latency,
                len(quiz_set.questions),
            ),
            validation_result=validation_result,
            quiz_set=quiz_set,
        )
        return QuizResponse(
            quiz_set=quiz_set,
            run_id=run_id,
            trace_id=trace_id,
            validation_status="passed" if validation_result["passed"] else "failed",
            coverage=coverage,
        )

    @staticmethod
    def _select_chunks(
        chunks: list[ChunkEntry], payload: QuizRequest
    ) -> tuple[list[ChunkEntry], QuizCoverage]:
        """Cover ready documents first, then expand or apply an explicit topic filter."""
        document_keys = {chunk.document_id or chunk.id for chunk in chunks}
        if payload.resource_scope == "topic":
            ranked = retrieve_local_chunks(
                chunks, payload.topic_query or "", limit=min(50, len(chunks))
            )
            retrieved = ranked[:50]
        else:
            first_by_document: dict[object, ChunkEntry] = {}
            for chunk in chunks:
                first_by_document.setdefault(chunk.document_id or chunk.id, chunk)
            retrieved = list(first_by_document.values())[:50]
            selected_ids = {chunk.id for chunk in retrieved}
            retrieved.extend(chunk for chunk in chunks if chunk.id not in selected_ids)
            retrieved = retrieved[:50]
        covered = {chunk.document_id or chunk.id for chunk in retrieved}
        coverage = QuizCoverage(
            documents_available=len(document_keys),
            documents_covered=len(covered),
            chunks_selected=len(retrieved),
            truncated=len(covered) < len(document_keys) or len(retrieved) < len(chunks),
        )
        return retrieved, coverage

    @staticmethod
    def _tool_calls(
        payload: QuizRequest,
        coverage: QuizCoverage,
        selection_latency: int,
        generation_latency: int,
        question_count: int,
    ) -> list[ToolCallTrace]:
        """Build measured retrieval and generation trace entries."""
        return [
            ToolCallTrace(
                id=uuid4(),
                tool_name="query_local_docs",
                input_summary={
                    "project_id": str(payload.project_id),
                    "resource_scope": payload.resource_scope,
                    "topic_query_length": len(payload.topic_query or ""),
                },
                output_summary=coverage.model_dump(),
                status="succeeded",
                latency_ms=selection_latency,
            ),
            ToolCallTrace(
                id=uuid4(),
                tool_name="generate_quiz",
                input_summary={
                    "schema": "QuizSet",
                    "requested_questions": (
                        payload.single_choice_count
                        + payload.fill_blank_count
                        + payload.subjective_count
                    ),
                },
                output_summary={
                    "questions": question_count,
                    "coverage": coverage.model_dump(),
                },
                status="succeeded",
                latency_ms=generation_latency,
            ),
        ]

    @staticmethod
    def _plan() -> ExecutionPlan:
        """Return the stable Quiz execution contract."""
        return ExecutionPlan(
            task_type=TaskType.QUIZ,
            allowed_tools=["query_local_docs", "generate_quiz"],
            requires_local_docs=True,
            requires_web=False,
            context_strategy="quiz",
            output_schema="QuizSet",
        )

    @staticmethod
    def _error(code: str, message: str, status_code: int) -> None:
        """Raise a stable Quiz application error."""
        raise QuizServiceError(code, message, status_code)
