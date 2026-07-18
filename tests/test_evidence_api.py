from uuid import uuid4

from fastapi.testclient import TestClient

from researchmate_api.config import Settings
from researchmate_api.main import create_app


HEADERS = {"Authorization": "Bearer dev-user-a"}
ADMIN_HEADERS = {"Authorization": "Bearer dev-admin"}


def client() -> TestClient:
    return TestClient(create_app(settings=Settings(app_env="test", llm_provider="fake")))


def create_project(api: TestClient) -> str:
    response = api.post("/api/v1/projects", headers=HEADERS, json={"name": "Evidence Review"})
    assert response.status_code == 201
    return response.json()["id"]


def research_payload(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "research_goal": "Compare the evidence for and against the proposed research claim.",
        "source_scope": {"document_ids": [], "allow_web": False},
        "pipeline_version_id": str(uuid4()),
        "review_policy": "strict",
    }


def test_research_run_is_owner_scoped_and_idempotent() -> None:
    api = client()
    project_id = create_project(api)
    payload = research_payload(project_id)
    command_headers = {**HEADERS, "Idempotency-Key": "research-run-0001"}

    first = api.post("/api/v1/research-runs", headers=command_headers, json=payload)
    repeated = api.post("/api/v1/research-runs", headers=command_headers, json=payload)

    assert first.status_code == 202
    assert repeated.status_code == 202
    assert repeated.json()["run_id"] == first.json()["run_id"]
    run_id = first.json()["run_id"]
    assert api.get(f"/api/v1/runs/{run_id}", headers=HEADERS).status_code == 200
    assert (
        api.get(
            f"/api/v1/runs/{run_id}",
            headers={"Authorization": "Bearer dev-user-b"},
        ).status_code
        == 404
    )


def test_idempotency_key_reuse_with_different_body_is_rejected() -> None:
    api = client()
    project_id = create_project(api)
    headers = {**HEADERS, "Idempotency-Key": "research-run-0002"}
    first = research_payload(project_id)
    second = {**first, "research_goal": "A different sufficiently long research objective for conflict proof."}

    assert api.post("/api/v1/research-runs", headers=headers, json=first).status_code == 202
    conflict = api.post("/api/v1/research-runs", headers=headers, json=second)

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_evaluation_and_reliability_require_privileged_identity() -> None:
    api = client()
    payload = {
        "dataset_id": str(uuid4()),
        "pipeline_version_id": str(uuid4()),
        "metrics": ["citation_precision"],
        "max_parallelism": 2,
    }

    denied = api.post(
        "/api/v1/evaluation-runs",
        headers={**HEADERS, "Idempotency-Key": "evaluation-0001"},
        json=payload,
    )
    accepted = api.post(
        "/api/v1/evaluation-runs",
        headers={**ADMIN_HEADERS, "Idempotency-Key": "evaluation-0001"},
        json=payload,
    )

    assert denied.status_code == 403
    assert accepted.status_code == 202
    assert api.get("/api/v1/dev/reliability", headers=HEADERS).status_code == 403
    assert api.get("/api/v1/dev/reliability", headers=ADMIN_HEADERS).status_code == 200


def test_evidence_routes_are_exposed_in_generated_openapi() -> None:
    paths = client().get("/openapi.json").json()["paths"]
    for path in (
        "/api/v1/research-runs",
        "/api/v1/runs/{run_id}",
        "/api/v1/runs/{run_id}/events",
        "/api/v1/runs/{run_id}/decisions",
        "/api/v1/projects/{project_id}/claims",
        "/api/v1/projects/{project_id}/claim-relations",
        "/api/v1/projects/{project_id}/reports",
        "/api/v1/reports/{report_id}/refresh",
        "/api/v1/evaluation-runs",
        "/api/v1/evaluation-runs/{evaluation_run_id}",
        "/api/v1/dev/reliability",
        "/api/v1/dev/fault-scenarios",
        "/api/v1/dev/fault-scenarios/{exercise_id}",
    ):
        assert path in paths


def test_fault_exercise_status_url_is_queryable_and_owner_scoped() -> None:
    api = client()
    accepted = api.post(
        "/api/v1/dev/fault-scenarios",
        headers={**ADMIN_HEADERS, "Idempotency-Key": "fault-exercise-0001"},
        json={"scenario": "llm_timeout", "duration_seconds": 5},
    )

    assert accepted.status_code == 202
    status_url = accepted.json()["status_url"]
    status = api.get(status_url, headers=ADMIN_HEADERS)
    assert status.status_code == 200
    assert status.json()["exercise_id"] == accepted.json()["exercise_id"]
    assert status.json()["status"] == "pending"
    assert api.get(status_url, headers=HEADERS).status_code == 403
