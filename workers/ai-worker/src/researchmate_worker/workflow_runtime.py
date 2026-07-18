from __future__ import annotations

from hashlib import sha256
import json
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Engine, text
from pydantic import BaseModel, Field, ValidationError

from researchmate_api.schemas.common import SourceType
from researchmate_api.services.evidence_generation import (
    ExtractedClaim,
    ReportProposal,
    build_research_plan,
    extract_claims,
    reconcile_claims,
    synthesize_report,
)
from researchmate_api.services.llm import ChatProvider
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.store import ChunkEntry
from researchmate_api.services.web_search import TavilyWebSearchProvider, WebSearchRequestError
from researchmate_worker.evidence_graph import EvidenceWorkflowState


class WorkflowRuntimeError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class WorkflowPipelineConfig(BaseModel):
    retrieval_limit: int = Field(default=12, ge=1, le=50)
    model: str = Field(min_length=1, max_length=200)
    evidence_prompt_version: str = Field(pattern=r"^evidence-review-v[0-9]+$")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


class SqlEvidenceWorkflowDomain:
    def __init__(
        self,
        *,
        engine: Engine,
        provider: ChatProvider,
        vector_store: QdrantHybridStore,
        pipeline_version: str,
        web_search: TavilyWebSearchProvider | None = None,
    ) -> None:
        self.engine = engine
        self.provider = provider
        self.vector_store = vector_store
        self.pipeline_version = pipeline_version
        self.web_search = web_search

    def bind_run(self, run_id: UUID) -> None:
        binder = getattr(self.provider, "bind_run", None)
        if binder is not None:
            binder(run_id)

    def initial_state(self, run_id: UUID, user_id: UUID) -> EvidenceWorkflowState:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    select r.id,r.user_id,r.project_id,r.kind,r.input,r.pipeline_version_id,
                      v.configuration
                    from workflow_runs r join pipeline_versions v on v.id=r.pipeline_version_id
                    where r.id=:run_id and r.user_id=:user_id
                      and r.kind in ('evidence_review','report_refresh') and v.status='accepted'
                    """
                ),
                {"run_id": run_id, "user_id": user_id},
            ).mappings().one_or_none()
            if row is None:
                raise WorkflowRuntimeError("RUN_NOT_FOUND")
            connection.execute(
                text(
                    """
                    update workflow_runs set status='running',started_at=coalesce(started_at,now()),
                      error_code=null where id=:run_id and status in ('pending','running')
                    """
                ),
                {"run_id": run_id},
            )
            self._event(
                connection,
                run_id,
                "workflow",
                "run_status_changed",
                "running",
                {"progress": 1},
            )
            run_input = row["input"]
            try:
                pipeline = WorkflowPipelineConfig.model_validate(row["configuration"])
            except ValidationError as exc:
                raise WorkflowRuntimeError("PIPELINE_CONFIGURATION_INVALID") from exc
            if getattr(self.provider, "model", pipeline.model) != pipeline.model:
                raise WorkflowRuntimeError("PIPELINE_MODEL_NOT_CONFIGURED")
            if pipeline.evidence_prompt_version != "evidence-review-v1":
                raise WorkflowRuntimeError("PIPELINE_PROMPT_NOT_SUPPORTED")
            source_scope = run_input.get("source_scope") or {}
            impacted_sections: list[str] = []
            research_goal = run_input.get("research_goal")
            if row["kind"] == "report_refresh":
                base_report_id = run_input.get("report_id")
                if not base_report_id:
                    raise WorkflowRuntimeError("REPORT_REFRESH_INPUT_INVALID")
                base = connection.execute(
                    text(
                        """
                        select title from reports
                        where id=:report_id and user_id=:user_id and project_id=:project_id
                        """
                    ),
                    {
                        "report_id": UUID(base_report_id),
                        "user_id": user_id,
                        "project_id": row["project_id"],
                    },
                ).scalar_one_or_none()
                if base is None:
                    raise WorkflowRuntimeError("REPORT_NOT_FOUND")
                requested = set(run_input.get("impacted_section_keys") or [])
                available = list(
                    connection.execute(
                        text(
                            """
                            select section_key from report_sections
                            where report_id=:report_id order by position
                            """
                        ),
                        {"report_id": UUID(base_report_id)},
                    ).scalars()
                )
                impacted_sections = [key for key in available if key in requested]
                if not impacted_sections or len(impacted_sections) != len(requested):
                    raise WorkflowRuntimeError("REPORT_SECTIONS_INVALID")
                research_goal = (
                    f"Incrementally refresh report '{base}' for these exact sections: "
                    + ", ".join(impacted_sections)
                )
        return EvidenceWorkflowState(
            run_id=str(run_id),
            user_id=str(user_id),
            project_id=str(row["project_id"]),
            research_goal=research_goal or "Refresh the affected report evidence.",
            review_policy=run_input.get("review_policy", "strict"),
            run_kind=row["kind"],
            base_report_id=str(run_input.get("report_id") or ""),
            impacted_section_keys=impacted_sections,
            changed_document_ids=list(run_input.get("changed_document_ids") or []),
            selected_document_ids=list(source_scope.get("document_ids") or []),
            allow_web=bool(source_scope.get("allow_web", False)),
            retrieval_limit=pipeline.retrieval_limit,
            pipeline_model=pipeline.model,
            evidence_prompt_version=pipeline.evidence_prompt_version,
            pipeline_version_ref=str(row["pipeline_version_id"]),
            evidence_batches=[],
        )

    def claim_delivery(self, run_id: UUID, worker_id: str, lease_seconds: int) -> bool:
        """Acquire one expiring workflow delivery lease; duplicate Celery deliveries are no-ops."""

        with self.engine.begin() as connection:
            claimed = connection.execute(
                text(
                    """
                    update workflow_runs set
                      lease_owner=:worker_id,
                      lease_expires_at=now() + make_interval(secs => :lease_seconds),
                      delivery_attempts=delivery_attempts + 1
                    where id=:run_id
                      and status in ('pending','running')
                      and (lease_expires_at is null or lease_expires_at < now()
                           or lease_owner=:worker_id)
                    returning id
                    """
                ),
                {
                    "run_id": run_id,
                    "worker_id": worker_id[:200],
                    "lease_seconds": lease_seconds,
                },
            ).one_or_none()
        return claimed is not None

    def release_delivery(self, run_id: UUID, worker_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update workflow_runs set lease_owner=null,lease_expires_at=null
                    where id=:run_id and lease_owner=:worker_id
                    """
                ),
                {"run_id": run_id, "worker_id": worker_id[:200]},
            )

    def record_retry(self, run_id: UUID, code: str, countdown: int) -> None:
        with self.engine.begin() as connection:
            self._event(
                connection,
                run_id,
                "workflow",
                "retry_scheduled",
                "pending",
                {"error_code": code[:120], "countdown_seconds": countdown},
            )

    def plan(self, state: EvidenceWorkflowState) -> dict[str, Any]:
        run_id = UUID(state["run_id"])
        self._node_started(run_id, "plan", 5)
        if state.get("run_kind") == "report_refresh":
            questions = [
                f"Re-evaluate evidence that can change report section '{section_key}'."
                for section_key in state.get("impacted_section_keys", [])
            ]
        else:
            questions = build_research_plan(self.provider, state["research_goal"]).questions
        self._node_completed(run_id, "plan", 15, {"question_count": len(questions)})
        return {"questions": questions}

    def retrieve_and_extract(self, state: EvidenceWorkflowState) -> dict[str, Any]:
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
        chunks = self._load_chunks(
            UUID(state["user_id"]), UUID(state["project_id"]), chunk_ids
        )
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
        batch = extract_claims(self.provider, question, chunks)
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
        run_id = UUID(state["run_id"])
        self._node_started(run_id, "reconcile", 50)
        batches = sorted(state.get("evidence_batches", []), key=lambda item: item["question_index"])
        claims = [claim for batch in batches for claim in batch["claims"]]
        proposals = [ExtractedClaim.model_validate(claim) for claim in claims]
        relations = reconcile_claims(self.provider, proposals)
        relation_values = [relation.model_dump(mode="json") for relation in relations.relations]
        self._node_completed(
            run_id,
            "reconcile",
            60,
            {"claim_count": len(claims), "relation_count": len(relation_values)},
        )
        return {"claims": claims, "relations": relation_values}

    def review_payload(self, state: EvidenceWorkflowState) -> dict[str, Any] | None:
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
                    text("update workflow_runs set status='waiting_human' where id=:id"),
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
        value = decision.get("decision")
        if value not in {"approve", "edit", "reject"}:
            raise WorkflowRuntimeError("DECISION_SCHEMA_INVALID")
        claims = list(state.get("claims", []))
        if value == "reject":
            rejected = set(state.get("review_payload", {}).get("flagged_claim_indices", []))
            rejected_chunks = set(
                state.get("review_payload", {}).get("suspicious_chunk_ids", [])
            )
            claims = [
                claim
                for index, claim in enumerate(claims, start=1)
                if index not in rejected
                and not rejected_chunks.intersection(claim.get("chunk_ids", []))
            ]
        elif value == "edit":
            edits = decision.get("edited_payload", {}).get("claim_text_edits", {})
            if not isinstance(edits, dict):
                raise WorkflowRuntimeError("EDIT_SCHEMA_INVALID")
            for raw_index, new_text in edits.items():
                index = int(raw_index) - 1
                if index < 0 or index >= len(claims) or not isinstance(new_text, str):
                    raise WorkflowRuntimeError("EDIT_SCHEMA_INVALID")
                claims[index] = {**claims[index], "text": new_text.strip(), "review_status": "edited"}
        if not claims:
            raise WorkflowRuntimeError("ALL_CLAIMS_REJECTED")
        with self.engine.begin() as connection:
            connection.execute(
                text("update workflow_runs set status='running' where id=:id"),
                {"id": UUID(state["run_id"])},
            )
        return {"claims": claims, "decision": decision}

    def synthesize(self, state: EvidenceWorkflowState) -> dict[str, Any]:
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
        run_id = UUID(state["run_id"])
        self._node_started(run_id, "validate_and_commit", 90)
        report = ReportProposal.model_validate(state["report"])
        if any(not claim.get("chunk_ids") for claim in state["claims"]):
            raise WorkflowRuntimeError("CLAIM_WITHOUT_EVIDENCE")
        self._commit(state, report)
        return {"validation": {"passed": True, "report_sections": len(report.sections)}}

    def resume_value(self, decision_id: UUID, run_id: UUID) -> dict[str, Any]:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    select decision,final_payload from human_decisions
                    where id=:decision_id and run_id=:run_id
                    """
                ),
                {"decision_id": decision_id, "run_id": run_id},
            ).mappings().one_or_none()
        if row is None:
            raise WorkflowRuntimeError("DECISION_NOT_FOUND")
        return {"decision": row["decision"], "edited_payload": row["final_payload"]}

    def mark_failed(self, run_id: UUID, code: str) -> None:
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

    def _load_chunks(
        self, user_id: UUID, project_id: UUID, chunk_ids: list[UUID]
    ) -> list[ChunkEntry]:
        if not chunk_ids:
            return []
        with self.engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    select id,user_id,project_id,document_id,source_type,source_title,text,
                      page_no,slide_no,url,created_at
                    from chunks where user_id=:user_id and project_id=:project_id
                      and id = any(:ids)
                    """
                ),
                {"user_id": user_id, "project_id": project_id, "ids": chunk_ids},
            ).mappings().all()
        by_id = {row["id"]: ChunkEntry(**dict(row)) for row in rows}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]

    def _commit(self, state: EvidenceWorkflowState, report: ReportProposal) -> None:
        run_id, user_id, project_id = (
            UUID(state["run_id"]),
            UUID(state["user_id"]),
            UUID(state["project_id"]),
        )
        with self.engine.begin() as connection:
            locked = connection.execute(
                text(
                    """
                    select status,kind,input from workflow_runs
                    where id=:id and user_id=:user_id and project_id=:project_id
                    for update
                    """
                ),
                {"id": run_id, "user_id": user_id, "project_id": project_id},
            ).mappings().one_or_none()
            if locked is None:
                raise WorkflowRuntimeError("WORKFLOW_OWNERSHIP_MISMATCH")
            if locked["status"] == "succeeded":
                return
            # Claim versions and report revisions are project-scoped sequences. Serialize
            # final commits for a project so concurrent runs cannot choose the same next
            # version and fail the unique(project_id, normalized_key, source_version)
            # constraint.
            connection.execute(
                text("select pg_advisory_xact_lock(hashtextextended(:key,1))"),
                {"key": str(project_id)},
            )
            connection.execute(text("delete from reports where source_run_id=:id"), {"id": run_id})
            connection.execute(text("delete from claims where source_run_id=:id"), {"id": run_id})
            connection.execute(
                text("delete from research_questions where source_run_id=:id"), {"id": run_id}
            )
            source_mode = "hybrid" if locked["input"].get("source_scope", {}).get("allow_web") else "local_only"
            connection.execute(
                text(
                    """
                    insert into ask_runs (
                      id,user_id,project_id,message,source_mode,task_type,resolved_mode,status,
                      validation_status,token_usage
                    ) values (
                      :id,:user_id,:project_id,:message,:mode,'answer',:mode,'succeeded',
                      'passed',cast(:usage as jsonb)
                    ) on conflict (id) do nothing
                    """
                ),
                {
                    "id": run_id,
                    "user_id": user_id,
                    "project_id": project_id,
                    "message": state["research_goal"],
                    "mode": source_mode,
                    "usage": _json({"workflow_run_id": str(run_id)}),
                },
            )
            question_ids = []
            for index, question in enumerate(state["questions"]):
                question_id = uuid5(NAMESPACE_URL, f"researchmate:{run_id}:question:{index}")
                question_ids.append(question_id)
                connection.execute(
                    text(
                        """
                        insert into research_questions (
                          id,user_id,project_id,source_run_id,question,status,priority,plan_order
                        ) values (
                          :id,:user_id,:project_id,:run_id,:question,'answered',0,:plan_order
                        )
                        """
                    ),
                    {
                        "id": question_id,
                        "user_id": user_id,
                        "project_id": project_id,
                        "run_id": run_id,
                        "question": question,
                        "plan_order": index,
                    },
                )
            chunks_by_id = {
                chunk["id"]: chunk
                for batch in state["evidence_batches"]
                for chunk in batch["chunks"]
            }
            citation_ids = {}
            for chunk_id, chunk in chunks_by_id.items():
                citation_id = uuid5(NAMESPACE_URL, f"researchmate:{run_id}:citation:{chunk_id}")
                citation_ids[chunk_id] = citation_id
                connection.execute(
                    text(
                        """
                        insert into citations (
                          id,ask_run_id,chunk_id,document_id,source_type,page_no,slide_no,url,quote
                        ) values (
                          :id,:run_id,:chunk_id,:document_id,:source_type,:page_no,:slide_no,:url,:quote
                        ) on conflict (id) do nothing
                        """
                    ),
                    {
                        "id": citation_id,
                        "run_id": run_id,
                        "chunk_id": (
                            UUID(chunk_id)
                            if chunk["source_type"] == SourceType.LOCAL_DOC.value
                            else None
                        ),
                        "document_id": UUID(chunk["document_id"]) if chunk["document_id"] else None,
                        "source_type": chunk["source_type"],
                        "page_no": chunk["page_no"],
                        "slide_no": chunk["slide_no"],
                        "url": chunk["url"],
                        "quote": chunk["text"][:1000],
                    },
                )
            claim_ids = []
            for index, claim in enumerate(state["claims"]):
                claim_id = uuid5(NAMESPACE_URL, f"researchmate:{run_id}:claim:{index}")
                claim_ids.append(claim_id)
                question_index = int(claim.get("question_index", 0))
                normalized_key = sha256(claim["text"].strip().lower().encode()).hexdigest()
                connection.execute(
                    text(
                        """
                        insert into claims (
                          id,user_id,project_id,question_id,source_run_id,text,normalized_key,
                          stance,confidence,review_status,source_version
                        ) values (
                          :id,:user_id,:project_id,:question_id,:run_id,:text,:normalized_key,
                          :stance,:confidence,:review_status,
                          coalesce((
                            select max(existing.source_version) + 1 from claims existing
                            where existing.project_id=:project_id
                              and existing.normalized_key=:normalized_key
                          ),1)
                        )
                        """
                    ),
                    {
                        "id": claim_id,
                        "user_id": user_id,
                        "project_id": project_id,
                        "question_id": question_ids[question_index],
                        "run_id": run_id,
                        "text": claim["text"],
                        "normalized_key": normalized_key,
                        "stance": claim["stance"],
                        "confidence": claim["confidence"],
                        "review_status": claim.get("review_status", "accepted"),
                    },
                )
                for chunk_id in claim["chunk_ids"]:
                    connection.execute(
                        text(
                            """
                            insert into claim_evidence (
                              claim_id,citation_id,relation,extraction_score,extractor_version
                            ) values (
                              :claim_id,:citation_id,'supports',:score,:version
                            )
                            """
                        ),
                        {
                            "claim_id": claim_id,
                            "citation_id": citation_ids[chunk_id],
                            "score": claim["confidence"],
                            "version": state.get("pipeline_version_ref") or self.pipeline_version,
                        },
                    )
            for relation in state.get("relations", []):
                connection.execute(
                    text(
                        """
                        insert into claim_relations (
                          source_claim_id,target_claim_id,relation,confidence,rationale_summary
                        ) values (
                          :source_id,:target_id,:relation,:confidence,:rationale
                        ) on conflict do nothing
                        """
                    ),
                    {
                        "source_id": claim_ids[relation["source_claim_id"] - 1],
                        "target_id": claim_ids[relation["target_claim_id"] - 1],
                        "relation": relation["relation"],
                        "confidence": relation["confidence"],
                        "rationale": relation["rationale_summary"],
                    },
                )
            report_id = uuid5(NAMESPACE_URL, f"researchmate:{run_id}:report")
            revision = connection.execute(
                text("select coalesce(max(revision),0)+1 from reports where project_id=:id"),
                {"id": project_id},
            ).scalar_one()
            sections_to_write: list[dict[str, Any]] = []
            report_title = report.title
            if locked["kind"] == "report_refresh":
                base_report_id = UUID(str(locked["input"].get("report_id")))
                base_report = connection.execute(
                    text(
                        """
                        select title from reports
                        where id=:id and user_id=:user_id and project_id=:project_id
                        for update
                        """
                    ),
                    {"id": base_report_id, "user_id": user_id, "project_id": project_id},
                ).scalar_one_or_none()
                if base_report is None:
                    raise WorkflowRuntimeError("REPORT_NOT_FOUND")
                report_title = base_report
                generated = {section.section_key: section for section in report.sections}
                impacted = list(locked["input"].get("impacted_section_keys") or [])
                if set(generated) != set(impacted):
                    raise WorkflowRuntimeError("REPORT_REFRESH_SECTION_MISMATCH")
                base_sections = connection.execute(
                    text(
                        """
                        select section_key,position,heading,body_markdown,evidence_snapshot,
                          validation_status
                        from report_sections where report_id=:id order by position
                        """
                    ),
                    {"id": base_report_id},
                ).mappings().all()
                for section in base_sections:
                    replacement = generated.get(section["section_key"])
                    if replacement is None:
                        sections_to_write.append(dict(section))
                        continue
                    sections_to_write.append(
                        {
                            "section_key": section["section_key"],
                            "position": section["position"],
                            "heading": replacement.heading,
                            "body_markdown": replacement.body_markdown,
                            "evidence_snapshot": {
                                "claim_ids": [
                                    str(claim_ids[index - 1])
                                    for index in replacement.claim_ids
                                ],
                                "source_run_id": str(run_id),
                                "refreshed_from_report_id": str(base_report_id),
                            },
                            "validation_status": "passed",
                        }
                    )
                connection.execute(
                    text("update reports set status='invalidated' where id=:id"),
                    {"id": base_report_id},
                )
            else:
                for position, section in enumerate(report.sections):
                    sections_to_write.append(
                        {
                            "section_key": section.section_key,
                            "position": position,
                            "heading": section.heading,
                            "body_markdown": section.body_markdown,
                            "evidence_snapshot": {
                                "claim_ids": [
                                    str(claim_ids[index - 1]) for index in section.claim_ids
                                ],
                                "source_run_id": str(run_id),
                            },
                            "validation_status": "passed",
                        }
                    )
            connection.execute(
                text(
                    """
                    insert into reports (
                      id,user_id,project_id,source_run_id,title,status,revision,
                      validation_status,generated_at
                    ) values (
                      :id,:user_id,:project_id,:run_id,:title,'published',:revision,'passed',now()
                    )
                    """
                ),
                {
                    "id": report_id,
                    "user_id": user_id,
                    "project_id": project_id,
                    "run_id": run_id,
                    "title": report_title,
                    "revision": revision,
                },
            )
            for section in sections_to_write:
                connection.execute(
                    text(
                        """
                        insert into report_sections (
                          report_id,section_key,position,heading,body_markdown,evidence_snapshot,
                          validation_status
                        ) values (
                          :report_id,:section_key,:position,:heading,:body,
                          cast(:snapshot as jsonb),:validation_status
                        )
                        """
                    ),
                    {
                        "report_id": report_id,
                        "section_key": section["section_key"],
                        "position": section["position"],
                        "heading": section["heading"],
                        "body": section["body_markdown"],
                        "snapshot": _json(section["evidence_snapshot"]),
                        "validation_status": section["validation_status"],
                    },
                )
            connection.execute(
                text(
                    """
                    update workflow_runs set status='succeeded',output=cast(:output as jsonb),
                      completed_at=now(),error_code=null where id=:id
                    """
                ),
                {"id": run_id, "output": _json({"report_id": str(report_id)})},
            )
            self._event(
                connection,
                run_id,
                "workflow",
                "run_status_changed",
                "succeeded",
                {"progress": 100, "report_id": str(report_id)},
            )

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
        connection,
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
