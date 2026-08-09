"""Record bounded workflow node and domain events for operator-visible progress."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from researchmate_worker.workflow_models import _json


class WorkflowEventsMixin:
    """Provide structured workflow event writes shared by execution and commit stages."""

    if TYPE_CHECKING:
        # Provided by sibling mixins composed in SqlEvidenceWorkflowDomain.
        engine: Engine

    def _node_started(self, run_id: UUID, node: str, progress: int) -> None:
        with self.engine.begin() as connection:
            self._event(
                connection,
                run_id,
                node,
                "node_started",
                "running",
                {"progress": progress},
            )

    def _node_completed(
        self, run_id: UUID, node: str, progress: int, payload: dict[str, Any]
    ) -> None:
        with self.engine.begin() as connection:
            self._event(
                connection,
                run_id,
                node,
                "node_completed",
                "succeeded",
                {"progress": progress, **payload},
            )

    @staticmethod
    def _event(
        connection: Connection,
        run_id: UUID,
        node: str,
        event_type: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        connection.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": str(run_id)},
        )
        connection.execute(
            text(
                """
                insert into run_events (
                  run_id,sequence,node_key,event_type,attempt,status,safe_payload
                ) values (
                  :run_id,coalesce((select max(sequence)+1 from run_events where run_id=:run_id),0),
                  :node,:event_type,1,:status,cast(:payload as jsonb)
                )
                """
            ),
            {
                "run_id": run_id,
                "node": node,
                "event_type": event_type,
                "status": status,
                "payload": _json(payload),
            },
        )
