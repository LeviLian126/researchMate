"""Persist owner-scoped answer feedback and immutable regression-set promotion."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from researchmate_api.persistence.evidence_base import _json
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.feedback import (
    AnswerFeedbackListResponse,
    AnswerFeedbackRecord,
    AnswerFeedbackUpsert,
    FeedbackEvidence,
    FeedbackPromotionCreate,
    FeedbackPromotionResult,
    FeedbackRating,
    feedback_source_type,
)
from researchmate_api.services.evidence_faults import EvidenceStoreError

FEEDBACK_DATASET_NAME = "Answer feedback regressions"
FEEDBACK_EVALUATION_BUDGET_USD = Decimal("1.000000")
FEEDBACK_EVALUATION_PARALLELISM = 4
FEEDBACK_EVALUATION_METRICS = (
    "evidence_recall",
    "citation_precision",
    "faithfulness",
)


def _normalize_feedback_evidence(value: object) -> list[FeedbackEvidence]:
    """Add source provenance to legacy trace candidates before schema validation."""
    if not isinstance(value, list):
        return []
    normalized: list[FeedbackEvidence] = []
    for raw in value:
        if not isinstance(raw, dict) or not raw.get("chunk_id"):
            continue
        item = {str(key): item_value for key, item_value in raw.items()}
        normalized.append(
            FeedbackEvidence.model_validate(
                {
                    "chunk_id": item["chunk_id"],
                    "source_type": feedback_source_type(
                        item.get("source_type"), item.get("document_id")
                    ),
                    "source_title": item.get("source_title"),
                    "page_no": item.get("page_no"),
                    "excerpt": item.get("score_context") or item.get("excerpt"),
                }
            )
        )
    return normalized


def _feedback_record(row: RowMapping) -> AnswerFeedbackRecord:
    """Map a bounded SQL row into the public feedback contract."""
    return AnswerFeedbackRecord(
        feedback_id=row["id"],
        ask_run_id=row["ask_run_id"],
        project_id=row["project_id"],
        conversation_id=row["conversation_id"],
        rating=row["rating"],
        category=row["category"],
        comment=row["comment"],
        question=row["question_snapshot"],
        answer=row["answer_snapshot"],
        citation_chunk_ids=list(row["citation_chunk_ids"] or []),
        retrieved_chunk_ids=list(row["retrieved_chunk_ids"] or []),
        retrieved_evidence=_normalize_feedback_evidence(row["retrieved_evidence"]),
        status=row["status"],
        promoted_case_id=row["promoted_case_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresEvidenceFeedbackMixin:
    """Own feedback snapshots, review listing, and atomic dataset version promotion."""

    if TYPE_CHECKING:
        from contextlib import AbstractContextManager

        _transaction: Callable[..., AbstractContextManager[Connection]]
        _append_outbox: Callable[..., None]

    def upsert_answer_feedback(
        self, user: CurrentUser, ask_run_id: UUID, payload: AnswerFeedbackUpsert
    ) -> AnswerFeedbackRecord | None:
        """Create or replace one feedback record after rechecking Ask ownership."""
        feedback_id = uuid4()
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                        with source as (
                          select r.user_id,r.project_id,r.conversation_id,r.message,
                            (select m.content from messages m
                             where m.ask_run_id=r.id and m.role='assistant'
                             order by m.created_at,m.id limit 1) answer,
                            array(select c.chunk_id from citations c
                                  where c.ask_run_id=r.id and c.chunk_id is not null
                                  order by c.created_at,c.id limit 80) citation_ids,
                            array(select (item->>'chunk_id')::uuid
                                  from jsonb_array_elements(coalesce(
                                    r.token_usage->'researchmate_trace'->'retrieved_chunks',
                                    '[]'::jsonb
                                  )) item
                                  where item ? 'chunk_id' limit 80) retrieved_ids,
                            coalesce(r.token_usage->'researchmate_trace'->'retrieved_chunks',
                                     '[]'::jsonb) retrieved_evidence
                          from ask_runs r join projects p on p.id=r.project_id
                          where r.id=:ask_run_id and r.user_id=:user_id
                            and r.status='succeeded' and r.conversation_id is not null
                            and p.user_id=:user_id and p.status='active' and p.deleted_at is null
                        )
                        insert into answer_feedback (
                          id,user_id,project_id,conversation_id,ask_run_id,rating,category,
                          comment,question_snapshot,answer_snapshot,citation_chunk_ids,
                          retrieved_chunk_ids,retrieved_evidence,status,promoted_case_id
                        )
                        select :id,user_id,project_id,conversation_id,:ask_run_id,:rating,
                          :category,:comment,message,answer,citation_ids,retrieved_ids,
                          retrieved_evidence,'new',null
                        from source where answer is not null
                        on conflict (user_id,ask_run_id) do update set
                          rating=excluded.rating,category=excluded.category,
                          comment=excluded.comment,question_snapshot=excluded.question_snapshot,
                          answer_snapshot=excluded.answer_snapshot,
                          citation_chunk_ids=excluded.citation_chunk_ids,
                          retrieved_chunk_ids=excluded.retrieved_chunk_ids,status='new',
                          retrieved_evidence=excluded.retrieved_evidence
                        returning *
                        """
                    ),
                    {
                        "id": feedback_id,
                        "user_id": user.id,
                        "ask_run_id": ask_run_id,
                        "rating": payload.rating,
                        "category": payload.category,
                        "comment": payload.comment,
                    },
                )
                .mappings()
                .one_or_none()
            )
        return _feedback_record(row) if row is not None else None

    def list_answer_feedback(
        self, user: CurrentUser, project_id: UUID, rating: FeedbackRating | None
    ) -> AnswerFeedbackListResponse | None:
        """List at most 100 feedback records for one active owner project."""
        with self._transaction(user) as connection:
            owned = connection.execute(
                text(
                    """
                    select 1 from projects where id=:project_id and user_id=:user_id
                      and status='active' and deleted_at is null
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).one_or_none()
            if owned is None:
                return None
            rows = (
                connection.execute(
                    text(
                        """
                        select * from answer_feedback
                        where user_id=:user_id and project_id=:project_id
                          and (cast(:rating as text) is null or rating=:rating)
                        order by updated_at desc limit 100
                        """
                    ),
                    {"user_id": user.id, "project_id": project_id, "rating": rating},
                )
                .mappings()
                .all()
            )
        return AnswerFeedbackListResponse(items=[_feedback_record(row) for row in rows])

    def promote_answer_feedback(
        self, user: CurrentUser, feedback_id: UUID, payload: FeedbackPromotionCreate
    ) -> FeedbackPromotionResult | None:
        """Atomically copy the prior set, append a reviewed case, and freeze a new version."""
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                        select * from answer_feedback
                        where id=:id and user_id=:user_id for update
                        """
                    ),
                    {"id": feedback_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            record = _feedback_record(row)
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
            connection.execute(
                text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": (f"{user.id}:{record.project_id}:{FEEDBACK_DATASET_NAME}")},
            )
            previous = (
                connection.execute(
                    text(
                        """
                        select id,version from evaluation_datasets
                        where user_id=:user_id and project_id=:project_id
                          and name=:name and status='frozen'
                        order by version desc limit 1 for update
                        """
                    ),
                    {
                        "user_id": user.id,
                        "project_id": record.project_id,
                        "name": FEEDBACK_DATASET_NAME,
                    },
                )
                .mappings()
                .one_or_none()
            )
            dataset_id, case_id = uuid4(), uuid4()
            version = int(previous["version"]) + 1 if previous is not None else 1
            connection.execute(
                text(
                    """
                    insert into evaluation_datasets (
                      id,user_id,project_id,name,version,description,status
                    ) values (
                      :id,:user_id,:project_id,:name,:version,:description,'draft'
                    )
                    """
                ),
                {
                    "id": dataset_id,
                    "user_id": user.id,
                    "project_id": record.project_id,
                    "name": FEEDBACK_DATASET_NAME,
                    "version": version,
                    "description": (
                        "Reviewer-promoted answer feedback for retrieval regression checks."
                    ),
                },
            )
            if previous is not None:
                connection.execute(
                    text(
                        """
                        insert into evaluation_cases (
                          id,dataset_id,case_key,input,expected_output,expected_evidence,labels
                        )
                        select gen_random_uuid(),:new_dataset_id,case_key,input,expected_output,
                          expected_evidence,labels from evaluation_cases
                        where dataset_id=:previous_dataset_id and case_key<>:case_key
                        """
                    ),
                    {
                        "new_dataset_id": dataset_id,
                        "previous_dataset_id": previous["id"],
                        "case_key": f"feedback-{feedback_id}",
                    },
                )
            labels = ["feedback-derived", record.category or record.rating]
            connection.execute(
                text(
                    """
                    insert into evaluation_cases (
                      id,dataset_id,case_key,input,expected_output,expected_evidence,labels
                    ) values (
                      :id,:dataset_id,:case_key,cast(:input as jsonb),null,
                      cast(:expected_evidence as jsonb),:labels
                    )
                    """
                ),
                {
                    "id": case_id,
                    "dataset_id": dataset_id,
                    "case_key": f"feedback-{feedback_id}",
                    "input": _json({"question": record.question}),
                    "expected_evidence": _json(
                        {"chunk_ids": [str(value) for value in payload.expected_chunk_ids]}
                    ),
                    "labels": labels,
                },
            )
            connection.execute(
                text("update evaluation_datasets set status='frozen' where id=:id"),
                {"id": dataset_id},
            )
            pipeline_version_id = connection.execute(
                text(
                    """
                    select id from pipeline_versions where status='accepted'
                    order by accepted_at desc nulls last,created_at desc limit 1
                    """
                )
            ).scalar_one_or_none()
            if pipeline_version_id is None:
                raise EvidenceStoreError("PIPELINE_NOT_ACCEPTED")
            case_count = int(
                connection.execute(
                    text("select count(*) from evaluation_cases where dataset_id=:id"),
                    {"id": dataset_id},
                ).scalar_one()
            )
            evaluation_run_id = uuid4()
            evaluation_summary = {
                "case_count": case_count,
                "metrics": FEEDBACK_EVALUATION_METRICS,
                "max_parallelism": FEEDBACK_EVALUATION_PARALLELISM,
                "max_cost_usd": str(FEEDBACK_EVALUATION_BUDGET_USD),
                "labels": ["feedback-regression", f"dataset-v{version}"],
                "trigger": "feedback_promotion",
            }
            connection.execute(
                text(
                    """
                    insert into evaluation_runs (
                      id,user_id,project_id,dataset_id,pipeline_version_id,status,
                      idempotency_key,summary,budget_limit_usd
                    ) values (
                      :id,:user_id,:project_id,:dataset_id,:pipeline_id,'pending',:key,
                      cast(:summary as jsonb),:budget_limit
                    )
                    """
                ),
                {
                    "id": evaluation_run_id,
                    "user_id": user.id,
                    "project_id": record.project_id,
                    "dataset_id": dataset_id,
                    "pipeline_id": pipeline_version_id,
                    "key": f"feedback-promotion:{dataset_id}:evaluation:v1",
                    "summary": _json(evaluation_summary),
                    "budget_limit": FEEDBACK_EVALUATION_BUDGET_USD,
                },
            )
            self._append_outbox(
                connection,
                aggregate_type="evaluation_run",
                aggregate_id=evaluation_run_id,
                event_type="evaluation.run.requested",
                payload={
                    "evaluation_run_id": str(evaluation_run_id),
                    "user_id": str(user.id),
                },
                idempotency_key=f"evaluation:{evaluation_run_id}:start:v1",
            )
            connection.execute(
                text(
                    """
                    update answer_feedback set status='promoted',promoted_case_id=:case_id
                    where id=:id and user_id=:user_id
                    """
                ),
                {"id": feedback_id, "user_id": user.id, "case_id": case_id},
            )
        return FeedbackPromotionResult(
            dataset_id=dataset_id,
            dataset_version=version,
            case_id=case_id,
            evaluation_run_id=evaluation_run_id,
            evaluation_status_url=f"/api/v1/evaluation-runs/{evaluation_run_id}",
        )
