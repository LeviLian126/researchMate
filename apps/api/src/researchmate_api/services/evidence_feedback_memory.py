"""Provide deterministic in-memory answer-feedback and dataset promotion behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.evidence import (
    EvaluationDatasetListResponse,
    EvaluationDatasetSummary,
)
from researchmate_api.schemas.feedback import (
    AnswerFeedbackListResponse,
    AnswerFeedbackRecord,
    AnswerFeedbackUpsert,
    FeedbackPromotionCreate,
    FeedbackPromotionResult,
    FeedbackRating,
)
from researchmate_api.services.evidence_faults import EvidenceStoreError

if TYPE_CHECKING:
    from researchmate_api.services._store_protocol import ResearchMateRepository


class MemoryEvidenceFeedbackMixin:
    """Own the local adapter's feedback snapshots and immutable dataset versions."""

    if TYPE_CHECKING:
        lock: RLock
        feedback_source: ResearchMateRepository | None
        answer_feedback: dict[tuple[UUID, UUID], AnswerFeedbackRecord]
        feedback_datasets: dict[UUID, tuple[UUID, EvaluationDatasetSummary]]
        feedback_cases: dict[UUID, list[UUID]]

    def list_evaluation_datasets(
        self, user: CurrentUser, project_id: UUID | None
    ) -> EvaluationDatasetListResponse:
        """Return frozen feedback-derived datasets available in the local adapter."""
        with self.lock:
            items = [
                summary
                for owner, summary in self.feedback_datasets.values()
                if owner == user.id and (project_id is None or summary.project_id == project_id)
            ]
        return EvaluationDatasetListResponse(
            items=sorted(items, key=lambda item: item.version, reverse=True)
        )

    def upsert_answer_feedback(
        self, user: CurrentUser, ask_run_id: UUID, payload: AnswerFeedbackUpsert
    ) -> AnswerFeedbackRecord | None:
        """Create or replace the caller's single feedback record for one owned answer."""
        if self.feedback_source is None:
            return None
        context = self.feedback_source.feedback_source_context(user, ask_run_id)
        if context is None:
            return None
        key = (user.id, ask_run_id)
        now = datetime.now(UTC)
        with self.lock:
            existing = self.answer_feedback.get(key)
            record = AnswerFeedbackRecord(
                feedback_id=existing.feedback_id if existing else uuid4(),
                ask_run_id=ask_run_id,
                project_id=context.project_id,
                conversation_id=context.conversation_id,
                rating=payload.rating,
                category=payload.category,
                comment=payload.comment,
                question=context.question,
                answer=context.answer,
                citation_chunk_ids=context.citation_chunk_ids,
                retrieved_chunk_ids=context.retrieved_chunk_ids,
                retrieved_evidence=context.retrieved_evidence,
                status="new",
                promoted_case_id=existing.promoted_case_id if existing else None,
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
            self.answer_feedback[key] = record
        self.feedback_source.set_feedback_rating(user, ask_run_id, payload.rating)
        return record

    def list_answer_feedback(
        self, user: CurrentUser, project_id: UUID, rating: FeedbackRating | None
    ) -> AnswerFeedbackListResponse | None:
        """List the developer's owner-scoped feedback review queue."""
        if (
            self.feedback_source is None
            or self.feedback_source.get_project(user, project_id) is None
        ):
            return None
        with self.lock:
            items = [
                record
                for (owner, _), record in self.answer_feedback.items()
                if owner == user.id
                and record.project_id == project_id
                and (rating is None or record.rating == rating)
            ]
        return AnswerFeedbackListResponse(
            items=sorted(items, key=lambda item: item.updated_at, reverse=True)[:100]
        )

    def promote_answer_feedback(
        self, user: CurrentUser, feedback_id: UUID, payload: FeedbackPromotionCreate
    ) -> FeedbackPromotionResult | None:
        """Snapshot reviewed feedback into the next immutable regression-set version."""
        with self.lock:
            record = next(
                (
                    item
                    for (owner, _), item in self.answer_feedback.items()
                    if owner == user.id and item.feedback_id == feedback_id
                ),
                None,
            )
            if record is None:
                return None
            if record.status == "promoted":
                raise EvidenceStoreError("FEEDBACK_ALREADY_PROMOTED")
            if record.rating != "not_helpful":
                raise EvidenceStoreError("FEEDBACK_NOT_BAD_CASE")
            replayable = {
                evidence.chunk_id
                for evidence in record.retrieved_evidence
                if evidence.source_type == "local_doc"
            }
            if not set(payload.expected_chunk_ids) <= replayable:
                raise EvidenceStoreError("EXPECTED_EVIDENCE_INVALID", status_code=422)
            previous = [
                summary
                for owner, summary in self.feedback_datasets.values()
                if owner == user.id
                and summary.project_id == record.project_id
                and summary.name == "Answer feedback regressions"
            ]
            latest = max(previous, key=lambda item: item.version) if previous else None
            dataset_id, case_id = uuid4(), uuid4()
            prior_cases = self.feedback_cases.get(latest.dataset_id, []) if latest else []
            if record.promoted_case_id is not None:
                prior_cases = [value for value in prior_cases if value != record.promoted_case_id]
            cases = [*prior_cases, case_id]
            version = (latest.version + 1) if latest else 1
            summary = EvaluationDatasetSummary(
                dataset_id=dataset_id,
                project_id=record.project_id,
                name="Answer feedback regressions",
                version=version,
                description="Reviewer-promoted answer feedback for retrieval regression checks.",
                case_count=len(cases),
            )
            self.feedback_datasets[dataset_id] = (user.id, summary)
            self.feedback_cases[dataset_id] = cases
            self.answer_feedback[(user.id, record.ask_run_id)] = record.model_copy(
                update={
                    "status": "promoted",
                    "promoted_case_id": case_id,
                    "updated_at": datetime.now(UTC),
                }
            )
            return FeedbackPromotionResult(
                dataset_id=dataset_id,
                dataset_version=version,
                case_id=case_id,
            )
