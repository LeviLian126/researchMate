"""Share deterministic API workflow fixtures and ready-document setup helpers."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

HEADERS = {"Authorization": "Bearer dev"}
USER_A_HEADERS = {"Authorization": "Bearer dev-user-a"}
USER_B_HEADERS = {"Authorization": "Bearer dev-user-b"}


def create_ready_document(client: TestClient, headers: dict[str, str] = HEADERS) -> tuple[str, str]:
    """Create a project and complete one deterministic local text document."""
    project_response = client.post("/api/v1/projects", json={"name": "RAG Study"}, headers=headers)
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    upload_response = client.post(
        "/api/v1/documents/upload-url",
        json={
            "project_id": project_id,
            "filename": "rag-notes.pdf",
            "file_type": "pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
        },
        headers=headers,
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]
    complete_response = client.post(
        f"/api/v1/documents/{document_id}/complete",
        json={},
        headers=headers,
    )
    assert complete_response.status_code == 202
    store = cast(FastAPI, client.app).state.store
    job = store.dev_complete_with_text(
        UUID(document_id),
        "RAG means retrieval augmented generation.\n"
        "A retriever selects relevant local chunks before generation.\n"
        "Citation validation ensures every answer points back to a source chunk.",
    )
    assert job is not None
    assert job.status == "succeeded"
    return project_id, document_id
