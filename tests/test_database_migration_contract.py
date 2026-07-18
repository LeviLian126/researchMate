import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "infra"
    / "supabase"
    / "migrations"
    / "202607150002_evidence_review_schema.sql"
)


def _migration_source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_additive_migration_defines_all_planned_tables() -> None:
    source = _migration_source()
    tables = set(
        re.findall(r"(?im)^create table if not exists\s+([a-z_]+)", source)
    )

    assert tables == {
        "workflow_runs",
        "run_events",
        "research_questions",
        "claims",
        "claim_evidence",
        "claim_relations",
        "reports",
        "report_sections",
        "human_decisions",
        "outbox_events",
        "pipeline_versions",
        "evaluation_datasets",
        "evaluation_cases",
        "evaluation_runs",
        "evaluation_scores",
    }


def test_migration_closes_initial_child_rls_gaps() -> None:
    source = _migration_source()
    required_policies = {
        "document_pages": "document_pages_owner_select",
        "tool_calls": "tool_calls_owner_select",
        "citations": "citations_owner_select",
        "quiz_questions": "quiz_questions_owner_select",
    }

    for table, policy in required_policies.items():
        assert f"create policy {policy} on {table}" in source
        assert "auth.uid()" in source


def test_planned_tables_have_rls_and_outbox_has_no_user_policy() -> None:
    source = _migration_source()
    tables = re.findall(
        r"(?im)^create table if not exists\s+([a-z_]+)", source
    )

    for table in tables:
        assert f"alter table {table} enable row level security" in source

    assert "idempotency_key text not null unique" in source
    assert "create policy outbox" not in source


def test_durable_run_and_evaluation_idempotency_are_unique_per_owner() -> None:
    source = _migration_source()

    for table in ("workflow_runs", "evaluation_runs"):
        table_sql = source.split(f"create table if not exists {table}", maxsplit=1)[1]
        table_sql = table_sql.split("create table if not exists", maxsplit=1)[0]
        assert "idempotency_key text not null" in table_sql
        assert "unique (user_id, idempotency_key)" in table_sql
