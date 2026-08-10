"""Exercise repaired Ask, Quiz, quota, and idempotency behavior through HTTP."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from researchmate_api.config import Settings
from researchmate_api.main import create_app
from researchmate_api.services.store import InMemoryResearchMateStore

HEADERS = {"Authorization": "Bearer dev-user-a"}


@pytest.fixture()
def client() -> TestClient:
    """Create an isolated in-memory API client with deterministic generation."""
    return TestClient(
        create_app(
            settings=Settings(
                app_env="test",
                llm_provider="fake",
                allow_dev_auth=True,
            ),
            repository=InMemoryResearchMateStore(),
        )
    )


def _ready_project(client: TestClient, text: str) -> str:
    """Create one workspace and complete a small local document."""
    project = client.post("/api/v1/projects", json={"name": "Regression"}, headers=HEADERS)
    assert project.status_code == 201
    project_id = project.json()["id"]
    upload = client.post(
        "/api/v1/documents/upload-url",
        json={
            "project_id": project_id,
            "filename": "notes.pdf",
            "file_type": "pdf",
            "mime_type": "application/pdf",
            "size_bytes": 128,
        },
        headers=HEADERS,
    )
    assert upload.status_code == 200
    completed = client.post(
        f"/api/v1/documents/{upload.json()['document_id']}/complete",
        json={},
        headers=HEADERS,
    )
    assert completed.status_code == 202
    store = cast(FastAPI, client.app).state.store
    job = store.dev_complete_with_text(UUID(upload.json()["document_id"]), text)
    assert job is not None
    return project_id


def test_invalid_conversation_does_not_consume_ask_quota(client: TestClient) -> None:
    """Reject an invalid conversation before the accepted-attempt quota boundary."""
    project_id = _ready_project(client, "RAG uses retrieval before generation.")
    # TestClient.app is typed as a generic ASGI app; cast to FastAPI to access state.
    store = cast(FastAPI, client.app).state.store
    usage_before = dict(store.api_usage)
    response = client.post(
        "/api/v1/ask",
        json={
            "project_id": project_id,
            "conversation_id": str(uuid4()),
            "message": "Explain RAG",
        },
        headers=HEADERS,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"
    assert store.api_usage == usage_before


def test_ask_idempotency_replays_without_duplicate_messages(client: TestClient) -> None:
    """Replay the first Ask response without charging or writing dialogue twice."""
    project_id = _ready_project(client, "RAG uses retrieval before generation.")
    headers = {**HEADERS, "Idempotency-Key": "ask-replay-0001"}
    payload = {"project_id": project_id, "message": "Explain RAG"}
    first = client.post("/api/v1/ask", json=payload, headers=headers)
    second = client.post("/api/v1/ask", json=payload, headers=headers)
    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    conversation_id = first.json()["conversation_id"]
    messages = client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=HEADERS
    ).json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert sum(cast(FastAPI, client.app).state.store.api_usage.values()) == 1


def test_idempotency_key_body_mismatch_returns_conflict(client: TestClient) -> None:
    """Reject a key reused for a different Ask body."""
    project_id = _ready_project(client, "RAG uses retrieval before generation.")
    headers = {**HEADERS, "Idempotency-Key": "ask-mismatch-01"}
    first = client.post(
        "/api/v1/ask",
        json={"project_id": project_id, "message": "Explain RAG"},
        headers=headers,
    )
    mismatch = client.post(
        "/api/v1/ask",
        json={"project_id": project_id, "message": "Explain citations"},
        headers=headers,
    )
    assert first.status_code == 200
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_quiz_default_instructions_work_for_chinese_documents(client: TestClient) -> None:
    """Generate from all ready resources without English keyword overlap."""
    project_id = _ready_project(
        client,
        "检索增强生成会先从资料中选择相关片段，再生成带引用的回答。",
    )
    response = client.post(
        "/api/v1/quiz",
        json={"project_id": project_id},
        headers={**HEADERS, "Idempotency-Key": "quiz-chinese-01"},
    )
    assert response.status_code == 200
    assert response.json()["quiz_set"]["questions"]
    assert response.json()["coverage"] == {
        "documents_available": 1,
        "documents_covered": 1,
        "chunks_selected": 1,
        "truncated": False,
    }


def test_quiz_idempotency_replays_the_same_aggregate(client: TestClient) -> None:
    """Return the same Quiz identifiers and keep one history entry on retry."""
    project_id = _ready_project(client, "RAG uses retrieval before generation.")
    headers = {**HEADERS, "Idempotency-Key": "quiz-replay-001"}
    payload = {"project_id": project_id}
    first = client.post("/api/v1/quiz", json=payload, headers=headers)
    second = client.post("/api/v1/quiz", json=payload, headers=headers)
    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    history = client.get(f"/api/v1/projects/{project_id}/quiz", headers=HEADERS).json()["quiz_sets"]
    assert len(history) == 1
