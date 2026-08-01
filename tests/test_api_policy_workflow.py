"""Verify API lifecycle, security validation, and developer-policy workflows."""

from fastapi.testclient import TestClient

from tests.api_workflow_support import (
    HEADERS,
    USER_A_HEADERS,
    USER_B_HEADERS,
    create_ready_document,
)

pytest_plugins = ["tests.api_workflow_fixtures"]


def test_conversation_rename_delete_and_cross_user_concealment(client: TestClient) -> None:
    """Enforce ownership across conversation rename and deletion operations."""
    project = client.post(
        "/api/v1/projects", json={"name": "Managed conversations"}, headers=USER_A_HEADERS
    ).json()
    conversation_id = client.post(
        "/api/v1/ask",
        json={"project_id": project["id"], "message": "Original title"},
        headers=USER_A_HEADERS,
    ).json()["conversation_id"]
    assert (
        client.patch(
            f"/api/v1/conversations/{conversation_id}",
            json={"title": "Other user's attempt"},
            headers=USER_B_HEADERS,
        ).status_code
        == 404
    )
    renamed = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "Renamed session"},
        headers=USER_A_HEADERS,
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed session"
    assert (
        client.patch(
            f"/api/v1/conversations/{conversation_id}",
            json={"title": "   "},
            headers=USER_A_HEADERS,
        ).status_code
        == 422
    )
    assert (
        client.delete(
            f"/api/v1/conversations/{conversation_id}", headers=USER_B_HEADERS
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/conversations/{conversation_id}", headers=USER_A_HEADERS
        ).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=USER_A_HEADERS
        ).status_code
        == 404
    )


def test_deleted_project_conceals_its_conversation_management(client: TestClient) -> None:
    """Conceal conversation operations after the owning project is deleted."""
    project = client.post(
        "/api/v1/projects", json={"name": "Deleted project"}, headers=USER_A_HEADERS
    ).json()
    conversation_id = client.post(
        "/api/v1/ask",
        json={"project_id": project["id"], "message": "Conversation before deletion"},
        headers=USER_A_HEADERS,
    ).json()["conversation_id"]
    assert (
        client.delete(f"/api/v1/projects/{project['id']}", headers=USER_A_HEADERS).status_code
        == 202
    )
    assert (
        client.patch(
            f"/api/v1/conversations/{conversation_id}",
            json={"title": "Should stay concealed"},
            headers=USER_A_HEADERS,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/conversations/{conversation_id}", headers=USER_A_HEADERS
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/conversations/{conversation_id}/messages", headers=USER_A_HEADERS
        ).status_code
        == 404
    )


def test_deleting_project_rejects_chat_and_quiz_before_consuming_usage(
    client: TestClient,
) -> None:
    """Reject work against deleting projects without charging daily quota."""
    project = client.post(
        "/api/v1/projects", json={"name": "Deleting project"}, headers=USER_A_HEADERS
    ).json()
    project_id = project["id"]
    repository = client.app.state.store
    project_key = next(key for key in repository.projects if str(key) == project_id)
    repository.projects[project_key] = repository.projects[project_key].model_copy(
        update={"status": "deleting"}
    )
    usage_before = dict(repository.api_usage)

    ask = client.post(
        "/api/v1/ask",
        json={"project_id": project_id, "message": "Do not charge this request"},
        headers=USER_A_HEADERS,
    )
    quiz = client.post(
        "/api/v1/quiz",
        json={"project_id": project_id, "prompt": "Do not charge this quiz"},
        headers=USER_A_HEADERS,
    )

    assert ask.status_code == 404
    assert quiz.status_code == 404
    assert repository.api_usage == usage_before


def test_runtime_rerank_config_is_admin_versioned(client: TestClient) -> None:
    """Require admin access and optimistic versioning for rerank configuration."""
    assert (
        client.get("/api/v1/admin/runtime-config/rerank", headers=USER_A_HEADERS).status_code == 403
    )
    current = client.get("/api/v1/admin/runtime-config/rerank", headers=HEADERS).json()
    updated = client.put(
        "/api/v1/admin/runtime-config/rerank",
        json={"provider": "deterministic", "expected_version": current["version"]},
        headers=HEADERS,
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == current["version"] + 1
    conflict = client.put(
        "/api/v1/admin/runtime-config/rerank",
        json={"provider": "nvidia", "expected_version": current["version"]},
        headers=HEADERS,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "RUNTIME_CONFIG_VERSION_CONFLICT"


def test_small_document_unrelated_query_abstains_without_citations(
    client: TestClient,
) -> None:
    """Require relevance even when every local chunk fits the context window."""
    project_id, _ = create_ready_document(client)
    response = client.post(
        "/api/v1/ask",
        json={"project_id": project_id, "message": "Explain photosynthesis chlorophyll"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["citations"] == []
    assert response.json()["sources"] == {"local_chunks": 0, "web_pages": 0}


def test_upload_rejects_mime_mismatch(client: TestClient) -> None:
    """Reject an upload whose declared extension and MIME type disagree."""
    project = client.post("/api/v1/projects", json={"name": "Security"}, headers=HEADERS)
    response = client.post(
        "/api/v1/documents/upload-url",
        json={
            "project_id": project.json()["id"],
            "filename": "malicious.pdf",
            "file_type": "pdf",
            "mime_type": "text/html",
            "size_bytes": 100,
        },
        headers=HEADERS,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_upload_completion_rejects_non_hex_checksum(client: TestClient) -> None:
    """Reject malformed checksums at the completion contract boundary."""
    project = client.post("/api/v1/projects", json={"name": "Checksum"}, headers=HEADERS)
    upload = client.post(
        "/api/v1/documents/upload-url",
        json={
            "project_id": project.json()["id"],
            "filename": "paper.pdf",
            "file_type": "pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
        },
        headers=HEADERS,
    )
    response = client.post(
        f"/api/v1/documents/{upload.json()['document_id']}/complete",
        json={"checksum_sha256": "z" * 64, "extracted_text": "valid local text"},
        headers=HEADERS,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_removed_source_selector_is_rejected(client: TestClient) -> None:
    """Reject obsolete source-selection fields instead of silently widening scope."""
    project = client.post("/api/v1/projects", json={"name": "Strict"}, headers=HEADERS)
    response = client.post(
        "/api/v1/ask",
        json={
            "project_id": project.json()["id"],
            "message": "Hello",
            "selected_mode": "local_only",
        },
        headers=HEADERS,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_executable_catalogs_and_report_detail_fail_closed_locally(
    client: TestClient,
) -> None:
    """Expose empty executable catalogs and conceal absent local reports."""
    pipelines = client.get("/api/v1/pipeline-versions", headers=HEADERS)
    datasets = client.get("/api/v1/evaluation-datasets", headers=HEADERS)
    missing_report = client.get(
        "/api/v1/reports/00000000-0000-4000-8000-000000000099",
        headers=HEADERS,
    )
    assert pipelines.status_code == 200
    assert pipelines.json() == {"items": []}
    assert datasets.status_code == 200
    assert datasets.json() == {"items": []}
    assert missing_report.status_code == 404
    assert missing_report.json()["error"]["code"] == "REPORT_NOT_FOUND"


def test_evaluation_catalog_requires_developer_role(client: TestClient) -> None:
    """Protect evaluation catalogs with the shared developer-role policy."""
    response = client.get("/api/v1/evaluation-datasets", headers=USER_A_HEADERS)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_REQUIRED"
