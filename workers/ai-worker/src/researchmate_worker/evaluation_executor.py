"""Execute one evaluation case against owned Qdrant evidence and the grounded LLM."""

from __future__ import annotations

from uuid import UUID

from researchmate_api.schemas.common import SourceType
from researchmate_api.services.answering import build_llm_grounded_answer
from researchmate_api.services.llm import ChatProvider
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.query_planning import plan_retrieval
from researchmate_api.services.store import ChunkEntry
from sqlalchemy import Engine, text

from researchmate_worker.evaluation_models import (
    ClaimedEvaluation,
    EvaluationCase,
    EvaluationRuntimeError,
    PipelineResult,
)

SUPPORTED_METRICS = {"schema_valid", "citation_precision", "evidence_recall", "faithfulness"}


class QdrantCaseExecutor:
    """Generate a grounded answer for one owned evaluation case."""

    def __init__(
        self, engine: Engine, vector_store: QdrantHybridStore, provider: ChatProvider
    ) -> None:
        self.engine = engine
        self.vector_store = vector_store
        self.provider = provider

    def execute(self, run: ClaimedEvaluation, case: EvaluationCase) -> PipelineResult:
        """Retrieve owned chunks and produce one normalized grounded result."""
        question = case.input.get("question")
        if not isinstance(question, str) or not question.strip():
            raise EvaluationRuntimeError("EVALUATION_CASE_INVALID")
        provider_settings = getattr(self.provider, "settings", None)
        if (
            provider_settings is None
            or getattr(provider_settings, "nvidia_model", None) != run.pipeline.model
        ):
            raise EvaluationRuntimeError("PIPELINE_MODEL_NOT_CONFIGURED")
        if run.pipeline.evaluation_prompt_version != "grounded-answer-v1":
            raise EvaluationRuntimeError("PIPELINE_PROMPT_NOT_SUPPORTED")
        retrieval_plan = plan_retrieval(
            question,
            [],
            corpus_tokens=1,
            full_context_limit=0,
            provider=None,
        )
        points = self.vector_store.query(
            user_id=str(run.user_id),
            project_id=str(run.project_id),
            source_type=SourceType.LOCAL_DOC,
            text=question,
            limit=run.pipeline.retrieval_limit,
            plan=retrieval_plan,
        )
        ids = []
        for point in points:
            try:
                ids.append(UUID(str(point.get("payload", {}).get("chunk_id"))))
            except (TypeError, ValueError):
                continue
        chunks = self._chunks(run, ids)
        if not chunks:
            raise EvaluationRuntimeError("EVIDENCE_NOT_FOUND")
        answer, citations, _, _provider_result = build_llm_grounded_answer(
            self.provider, question, chunks
        )
        return PipelineResult(
            response=answer,
            contexts=[chunk.text for chunk in chunks],
            retrieved_chunk_ids=[str(chunk.id) for chunk in chunks],
            cited_chunk_ids=[str(citation.chunk_id) for citation in citations if citation.chunk_id],
        )

    def _chunks(self, run: ClaimedEvaluation, ids: list[UUID]) -> list[ChunkEntry]:
        if not ids:
            return []
        with self.engine.begin() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    select id,user_id,project_id,document_id,source_type,source_title,text,
                           page_no,slide_no,url,section_title,section_path,chunk_index,
                           char_start,char_end,metadata,created_at
                    from chunks where user_id=:user_id and project_id=:project_id and id=any(:ids)
                    """
                    ),
                    {"user_id": run.user_id, "project_id": run.project_id, "ids": ids},
                )
                .mappings()
                .all()
            )
        by_id = {row["id"]: ChunkEntry(**dict(row)) for row in rows}
        return [by_id[value] for value in ids if value in by_id]
