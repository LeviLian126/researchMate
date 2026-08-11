"""Project trusted Ask context into the answer-feedback workflow."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.feedback import (
    FeedbackEvidence,
    FeedbackRating,
    FeedbackSourceContext,
    feedback_source_type,
)


class PostgresFeedbackSourceMixin:
    """Read trusted feedback source snapshots and confirm persisted ratings."""

    if TYPE_CHECKING:
        from contextlib import AbstractContextManager

        _transaction: Callable[..., AbstractContextManager[Connection]]

    def feedback_source_context(
        self, user: CurrentUser, run_id: UUID
    ) -> FeedbackSourceContext | None:
        """Return persisted answer context after enforcing Ask and project ownership."""
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                        select r.id,r.user_id,r.project_id,r.conversation_id,r.message,
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
                                )) item where item ? 'chunk_id' limit 80) retrieved_ids,
                          coalesce(r.token_usage->'researchmate_trace'->'retrieved_chunks',
                                   '[]'::jsonb) retrieved_evidence
                        from ask_runs r join projects p on p.id=r.project_id
                        where r.id=:run_id and r.user_id=:user_id
                          and r.conversation_id is not null and r.status='succeeded'
                          and p.user_id=:user_id and p.status='active' and p.deleted_at is null
                        """
                    ),
                    {"run_id": run_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None or row["answer"] is None:
            return None
        return FeedbackSourceContext(
            ask_run_id=row["id"],
            user_id=row["user_id"],
            project_id=row["project_id"],
            conversation_id=row["conversation_id"],
            question=row["message"],
            answer=row["answer"],
            citation_chunk_ids=list(row["citation_ids"] or []),
            retrieved_chunk_ids=list(row["retrieved_ids"] or []),
            retrieved_evidence=[
                FeedbackEvidence(
                    chunk_id=item["chunk_id"],
                    source_type=feedback_source_type(
                        item.get("source_type"), item.get("document_id")
                    ),
                    source_title=item.get("source_title"),
                    page_no=item.get("page_no"),
                    excerpt=item.get("score_context"),
                )
                for item in row["retrieved_evidence"]
            ],
        )

    def set_feedback_rating(self, user: CurrentUser, run_id: UUID, rating: FeedbackRating) -> bool:
        """Confirm the persisted feedback row used by conversation-history projection."""
        with self._transaction(user) as connection:
            found = connection.execute(
                text(
                    """
                    select 1 from answer_feedback
                    where user_id=:user_id and ask_run_id=:run_id and rating=:rating
                    """
                ),
                {"user_id": user.id, "run_id": run_id, "rating": rating},
            ).one_or_none()
        return found is not None
