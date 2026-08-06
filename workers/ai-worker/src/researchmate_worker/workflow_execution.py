"""Implement evidence workflow planning, retrieval, review, and synthesis decisions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from researchmate_api.schemas.common import SourceType
from researchmate_api.services.evidence_generation import (
    ExtractedClaim,
    ReportProposal,
    synthesize_report,
)
from researchmate_api.services.web_search import (
    WebSearchRequestError,
)
from sqlalchemy import text

from researchmate_worker.evidence_graph import EvidenceWorkflowState
from researchmate_worker.workflow_models import WorkflowRuntimeError


class WorkflowExecutionMixin:
    """Provide provider-facing workflow decisions independently from SQL commit mechanics."""

    def plan(self, state: EvidenceWorkflowState) -> dict[str, Any]:
        """Create provider-backed questions or preserve exact refresh sections."""
        run_id = UUID(state["run_id"])
        self._node_started(run_id, "plan", 5)
        if state.get("run_kind") == "report_refresh":
            questions = [
                f"Re-evaluate evidence that can change report section '{section_key}'."
                for section_key in state.get("impacted_section_keys", [])
            ]
        else:
            from researchmate_worker import workflow_runtime

            questions = workflow_runtime.build_research_plan(
                self.provider, state["research_goal"]
            ).questions
        self._node_completed(run_id, "plan", 15, {"question_count": len(questions)})
        return {"questions": questions}

    def retrieve_and_extract(self, state: EvidenceWorkflowState) -> dict[str, Any]:
        """Retrieve owned evidence and extract claims with server-controlled provenance."""
        run_id = UUID(state["run_id"])
        question = state["question"]
        question_index = state["question_index"]
        node_key = f"retrieve_extract:{question_index}"
        self._node_started(run_id, node_key, 20)
        selected_documents = (
            state.get("changed_document_ids")
            if state.get("run_kind") == "report_refresh"
            else state.get("selected_document_ids")
        )
        points = self.vector_store.query(
            user_id=state["user_id"],
            project_id=state["project_id"],
            source_type=SourceType.LOCAL_DOC,
            text=question,
            limit=int(state.get("retrieval_limit", 12)),
            document_ids=selected_documents or None,
        )
        chunk_ids = []
        for point in points:
            raw_id = point.get("payload", {}).get("chunk_id")
            try:
                chunk_ids.append(UUID(str(raw_id)))
            except (TypeError, ValueError):
                continue
        chunks = self._load_chunks(UUID(state["user_id"]), UUID(state["project_id"]), chunk_ids)
        if state.get("allow_web"):
            if self.web_search is None:
                raise WorkflowRuntimeError("WEB_SEARCH_NOT_CONFIGURED")
            try:
                chunks.extend(
                    self.web_search.search(
                        user_id=UUID(state["user_id"]),
                        project_id=UUID(state["project_id"]),
                        query=question,
                        limit=5,
                    )
                )
            except WebSearchRequestError as exc:
                raise WorkflowRuntimeError(
                    "WEB_SEARCH_UNAVAILABLE", retryable=exc.retryable
                ) from exc
        chunks = list({chunk.id: chunk for chunk in chunks}.values())
        if not chunks:
            raise WorkflowRuntimeError("EVIDENCE_NOT_FOUND")
        from researchmate_worker import workflow_runtime

        batch = workflow_runtime.extract_claims(self.provider, question, chunks)
        serialized_chunks = [
            {
                "id": str(chunk.id),
                "document_id": str(chunk.document_id) if chunk.document_id else None,
                "source_type": chunk.source_type.value,
                "source_title": chunk.source_title,
                "text": chunk.text,
                "page_no": chunk.page_no,
                "slide_no": chunk.slide_no,
                "url": chunk.url,
            }
            for chunk in chunks
        ]
        serialized_claims = []
        for claim in batch.claims:
            serialized_claims.append(
                {
                    **claim.model_dump(mode="json"),
                    "chunk_ids": [str(chunks[index - 1].id) for index in claim.evidence_ids],
                    "question_index": question_index,
                }
            )
        self._node_completed(
            run_id,
            node_key,
            45,
            {"evidence_count": len(chunks), "claim_count": len(serialized_claims)},
        )
        return {
            "evidence_batches": [
                {
                    "question_index": question_index,
                    "question": question,
                    "chunks": serialized_chunks,
                    "claims": serialized_claims,
                }
            ]
        }

    def reconcile(self, state: EvidenceWorkflowState) -> dict[str, Any]:
        """Derive claim relationships without changing the underlying evidence."""
        run_id = UUID(state["run_id"])
        self._node_started(run_id, "reconcile", 50)
        batches = sorted(state.get("evidence_batches", []), key=lambda item: item["question_index"])
        claims = [claim for batch in batches for claim in batch["claims"]]
        proposals = [ExtractedClaim.model_validate(claim) for claim in claims]
        from researchmate_worker import workflow_runtime

        relations = workflow_runtime.reconcile_claims(self.provider, proposals)
        relation_values = [relation.model_dump(mode="json") for relation in relations.relations]
        self._node_completed(
            run_id,
            "reconcile",
            60,
            {"claim_count": len(claims), "relation_count": len(relation_values)},
        )
        return {"claims": claims, "relations": relation_values}

    def review_payload(self, state: EvidenceWorkflowState) -> dict[str, Any] | None:
        """Request human review only when confidence or source trust requires it."""
        flagged = [
            index
            for index, claim in enumerate(state.get("claims", []), start=1)
            if float(claim["confidence"]) < 0.75
        ]
        suspicious_sources = []
        markers = ("ignore previous", "system prompt", "assistant:", "developer message")
        for batch in state.get("evidence_batches", []):
            for chunk in batch["chunks"]:
                if chunk["source_type"] == SourceType.WEB_PAGE.value or any(
                    marker in chunk["text"].lower() for marker in markers
                ):
                    suspicious_sources.append(chunk["id"])
        if state.get("review_policy") != "strict" and not suspicious_sources:
            return None
        if not flagged and not suspicious_sources:
            return None
        payload = {
            "interrupt_key": "evidence-review-v1",
            "reason": "low_confidence_or_untrusted_source",
            "flagged_claim_indices": flagged,
            "suspicious_chunk_ids": suspicious_sources,
            "allowed_decisions": ["approve", "edit", "reject"],
        }
        run_id = UUID(state["run_id"])
        with self.engine.begin() as connection:
            existing = connection.execute(
                text(
                    """
                    select 1 from run_events where run_id=:run_id
                      and event_type='human_requested'
                      and safe_payload->>'interrupt_key'=:interrupt_key
                    """
                ),
                {"run_id": run_id, "interrupt_key": payload["interrupt_key"]},
            ).one_or_none()
            if existing is None:
                connection.execute(
                text("update workflow_runs set status='waiting_human' where id=:id and status='running'"),
                    {"id": run_id},
                )
                self._event(
                    connection,
                    run_id,
                    "human_review",
                    "human_requested",
                    "waiting_human",
                    payload,
                )
        return payload

    def apply_decision(
        self, state: EvidenceWorkflowState, decision: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply only approved human edits or rejections to review-scoped claims."""
        value = decision.get("decision")
        if value not in {"approve", "edit", "reject"}:
            raise WorkflowRuntimeError("DECISION_SCHEMA_INVALID")
        claims = list(state.get("claims", []))
        if value == "reject":
            rejected = set(state.get("review_payload", {}).get("flagged_claim_indices", []))
            rejected_chunks = set(state.get("review_payload", {}).get("suspicious_chunk_ids", []))
            claims = [
                claim
                for index, claim in enumerate(claims, start=1)
                if index not in rejected
                and not rejected_chunks.intersection(claim.get("chunk_ids", []))
            ]
        elif value == "edit":
            edited_payload = decision.get("edited_payload")
            if not isinstance(edited_payload, dict):
                raise WorkflowRuntimeError("EDIT_SCHEMA_INVALID")
            edits = edited_payload.get("claim_text_edits", {})
            if not isinstance(edits, dict):
                raise WorkflowRuntimeError("EDIT_SCHEMA_INVALID")
            for raw_index, new_text in edits.items():
                try:
                    index = int(raw_index) - 1
                except (TypeError, ValueError) as exc:
                    raise WorkflowRuntimeError("EDIT_SCHEMA_INVALID") from exc
                if (
                    index < 0
                    or index >= len(claims)
                    or not isinstance(new_text, str)
                    or not new_text.strip()
                ):
                    raise WorkflowRuntimeError("EDIT_SCHEMA_INVALID")
                claims[index] = {
                    **claims[index],
                    "text": new_text.strip(),
                    "review_status": "edited",
                }
        if not claims:
            raise WorkflowRuntimeError("ALL_CLAIMS_REJECTED")
        with self.engine.begin() as connection:
            connection.execute(
                text("update workflow_runs set status='running' where id=:id"),
                {"id": UUID(state["run_id"])},
            )
        return {"claims": claims, "decision": decision}

    def synthesize(self, state: EvidenceWorkflowState) -> dict[str, Any]:
        """Build a report proposal constrained to reviewed claims and section scope."""
        run_id = UUID(state["run_id"])
        self._node_started(run_id, "synthesize", 70)
        claims = [ExtractedClaim.model_validate(claim) for claim in state["claims"]]
        required_keys = (
            state.get("impacted_section_keys")
            if state.get("run_kind") == "report_refresh"
            else None
        )
        report = synthesize_report(
            self.provider,
            state["research_goal"],
            claims,
            required_section_keys=required_keys,
        )
        self._node_completed(run_id, "synthesize", 85, {"sections": len(report.sections)})
        return {"report": report.model_dump(mode="json")}

    def validate_and_commit(self, state: EvidenceWorkflowState) -> dict[str, Any]:
        """Reject ungrounded claims before atomically committing the report."""
        run_id = UUID(state["run_id"])
        self._node_started(run_id, "validate_and_commit", 90)
        report = ReportProposal.model_validate(state["report"])
        if any(not claim.get("chunk_ids") for claim in state["claims"]):
            raise WorkflowRuntimeError("CLAIM_WITHOUT_EVIDENCE")
        self._commit(state, report)
        return {"validation": {"passed": True, "report_sections": len(report.sections)}}

    def resume_value(self, decision_id: UUID, run_id: UUID) -> dict[str, Any]:
        """Load one persisted human decision scoped to the active workflow run."""
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        """
                    select decision,final_payload from human_decisions
                    where id=:decision_id and run_id=:run_id
                    """
                    ),
                    {"decision_id": decision_id, "run_id": run_id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise WorkflowRuntimeError("DECISION_NOT_FOUND")
        return {"decision": row["decision"], "edited_payload": row["final_payload"]}

    def mark_failed(self, run_id: UUID, code: str) -> None:
        """Make a workflow failure terminal and release its delivery lease."""
        with self.engine.begin() as connection:
            updated = connection.execute(
                text(
                    """
                    update workflow_runs set status='failed',error_code=:code,completed_at=now(),
                      lease_owner=null,lease_expires_at=null
                    where id=:id and status not in ('succeeded','cancelled')
                    returning id
                    """
                ),
                {"id": run_id, "code": code[:120]},
            ).one_or_none()
            if updated is None:
                return
            self._event(
                connection,
                run_id,
                "workflow",
                "run_status_changed",
                "failed",
                {"progress": 100, "error_code": code[:120]},
            )
