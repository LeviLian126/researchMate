"""Atomically commit validated reports, sections, claims, and provenance."""

from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import NAMESPACE_URL, UUID, uuid5

from researchmate_api.schemas.common import SourceType
from researchmate_api.services.evidence_generation import ReportProposal
from sqlalchemy import text

from researchmate_worker.evidence_graph import EvidenceWorkflowState
from researchmate_worker.workflow_loader import WorkflowEvidenceLoaderMixin
from researchmate_worker.workflow_models import WorkflowRuntimeError, _json


class WorkflowCommitMixin(WorkflowEvidenceLoaderMixin):
    """Persist one workflow outcome within a single database transaction boundary."""

    if TYPE_CHECKING:
        # Provided by sibling mixins composed in SqlEvidenceWorkflowDomain.
        from collections.abc import Callable

        from sqlalchemy import Connection, Engine

        engine: Engine
        pipeline_version: str
        _event: Callable[..., None]

    def _commit(self, state: EvidenceWorkflowState, report: ReportProposal) -> None:
        run_id = UUID(state.get("run_id", ""))
        user_id = UUID(state.get("user_id", ""))
        project_id = UUID(state.get("project_id", ""))
        with self.engine.begin() as connection:
            locked = (
                connection.execute(
                    text(
                        """
                    select status,kind,input from workflow_runs
                    where id=:id and user_id=:user_id and project_id=:project_id
                    for update
                    """
                    ),
                    {"id": run_id, "user_id": user_id, "project_id": project_id},
                )
                .mappings()
                .one_or_none()
            )
            if locked is None:
                raise WorkflowRuntimeError("WORKFLOW_OWNERSHIP_MISMATCH")
            if locked["status"] in ("succeeded", "failed", "cancelled"):
                return
            # Serialize project commits so claim versions and report revisions stay unique.
            connection.execute(
                text("select pg_advisory_xact_lock(hashtextextended(:key,1))"),
                {"key": str(project_id)},
            )
            connection.execute(text("delete from reports where source_run_id=:id"), {"id": run_id})
            connection.execute(text("delete from claims where source_run_id=:id"), {"id": run_id})
            connection.execute(
                text("delete from research_questions where source_run_id=:id"), {"id": run_id}
            )
            web_enabled = bool(locked["input"].get("source_scope", {}).get("allow_web"))
            connection.execute(
                text(
                    """
                    insert into ask_runs (
                      id,user_id,project_id,message,task_type,web_enabled,context_strategy,
                      status,validation_status,token_usage
                    ) values (
                      :id,:user_id,:project_id,:message,'answer',:web_enabled,
                      :context_strategy,'succeeded','passed',cast(:usage as jsonb)
                    ) on conflict (id) do nothing
                    """
                ),
                {
                    "id": run_id,
                    "user_id": user_id,
                    "project_id": project_id,
                    "message": state.get("research_goal", ""),
                    "web_enabled": web_enabled,
                    "context_strategy": (
                        "hybrid_retrieval_web" if web_enabled else "hybrid_retrieval"
                    ),
                    "usage": _json({"workflow_run_id": str(run_id)}),
                },
            )
            question_ids = []
            for index, question in enumerate(state.get("questions", [])):
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
                for batch in state.get("evidence_batches", [])
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
            for index, claim in enumerate(state.get("claims", [])):
                claim_id = uuid5(NAMESPACE_URL, f"researchmate:{run_id}:claim:{index}")
                claim_ids.append(claim_id)
                question_index = int(claim.get("question_index", 0))
                if question_index < 0 or question_index >= len(question_ids):
                    raise WorkflowRuntimeError("CLAIM_INDEX_OUT_OF_RANGE")
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
                source_idx = relation["source_claim_id"] - 1
                target_idx = relation["target_claim_id"] - 1
                if not 0 <= source_idx < len(claim_ids) or not 0 <= target_idx < len(claim_ids):
                    raise WorkflowRuntimeError("RELATION_INDEX_OUT_OF_RANGE")
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
                        "source_id": claim_ids[source_idx],
                        "target_id": claim_ids[target_idx],
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
                base_sections = (
                    connection.execute(
                        text(
                            """
                        select section_key,position,heading,body_markdown,evidence_snapshot,
                          validation_status
                        from report_sections where report_id=:id order by position
                        """
                        ),
                        {"id": base_report_id},
                    )
                    .mappings()
                    .all()
                )
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
                                    str(claim_ids[index - 1]) for index in replacement.claim_ids
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
