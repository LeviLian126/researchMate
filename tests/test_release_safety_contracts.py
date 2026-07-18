from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_evaluation_budget_and_fault_audit_migration_is_fail_closed() -> None:
    source = (
        ROOT
        / "infra"
        / "supabase"
        / "migrations"
        / "202607150005_evaluation_budget_and_fault_exercises.sql"
    ).read_text(encoding="utf-8").lower()

    assert "budget_limit_usd" in source
    assert "budget_reserved_usd <= budget_limit_usd" in source
    assert "create table if not exists fault_exercises" in source
    assert "duration_seconds between 1 and 60" in source
    assert "alter table fault_exercises enable row level security" in source


def test_runtime_readiness_and_workflow_budget_migration_is_fail_closed() -> None:
    source = (
        ROOT
        / "infra"
        / "supabase"
        / "migrations"
        / "202607160006_runtime_readiness_and_workflow_budget.sql"
    ).read_text(encoding="utf-8").lower()

    assert "create table if not exists runtime_heartbeats" in source
    assert "revoke all on runtime_heartbeats from anon, authenticated" in source
    assert "budget_reserved_usd <= budget_limit_usd" in source
    assert "lease_expires_at" in source
    assert "status = 'accepted'" in source


def test_workflow_claim_versions_are_serialized_and_incremented() -> None:
    source = (
        ROOT
        / "workers"
        / "ai-worker"
        / "src"
        / "researchmate_worker"
        / "workflow_runtime.py"
    ).read_text(encoding="utf-8").lower()

    assert "pg_advisory_xact_lock(hashtextextended(:key,1))" in source
    assert "max(existing.source_version) + 1" in source
    assert "workflow_ownership_mismatch" in source
    assert ":review_status,1" not in source


def test_report_refresh_filters_changed_documents_and_preserves_unaffected_sections() -> None:
    repository = (
        ROOT
        / "apps"
        / "api"
        / "src"
        / "researchmate_api"
        / "persistence"
        / "evidence_postgres.py"
    ).read_text(encoding="utf-8").lower()
    workflow = (
        ROOT
        / "workers"
        / "ai-worker"
        / "src"
        / "researchmate_worker"
        / "workflow_runtime.py"
    ).read_text(encoding="utf-8").lower()

    assert "jsonb_array_elements_text" in repository
    assert "c.document_id=any(:document_ids)" in repository
    assert 'state.get("changed_document_ids")' in workflow
    assert 'state.get("selected_document_ids")' in workflow
    assert "document_ids=selected_documents or none" in workflow
    assert "refreshed_from_report_id" in workflow
    assert "update reports set status='invalidated'" in workflow
    assert "report_refresh_section_mismatch" in workflow
