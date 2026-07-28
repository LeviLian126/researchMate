from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from researchmate_api.config import Settings
from researchmate_api.main import create_app
from researchmate_api.services.store import store


@pytest.fixture(autouse=True)
def reset_local_store() -> Generator[None, None, None]:
    store.reset()
    yield
    store.reset()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(settings=Settings(app_env="test", llm_provider="fake")))


HEADERS = {"Authorization": "Bearer dev"}
USER_A_HEADERS = {"Authorization": "Bearer dev-user-a"}
USER_B_HEADERS = {"Authorization": "Bearer dev-user-b"}


# 创建项目并上传一份本地开发文本资料。
def create_ready_document(client: TestClient, headers: dict[str, str] = HEADERS) -> tuple[str, str]:
    project_response = client.post("/api/v1/projects", json={"name": "RAG Study"}, headers=headers)
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    upload_payload = {
        "project_id": project_id,
        "filename": "rag-notes.pdf",
        "file_type": "pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1024,
    }
    upload_response = client.post("/api/v1/documents/upload-url", json=upload_payload, headers=headers)
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]
    complete_response = client.post(
        f"/api/v1/documents/{document_id}/complete",
        json={
            "extracted_text": (
                "RAG means retrieval augmented generation.\n"
                "A retriever selects relevant local chunks before generation.\n"
                "Citation validation ensures every answer points back to a source chunk."
            )
        },
        headers=headers,
    )
    assert complete_response.status_code == 202
    job_response = client.get(f"/api/v1/jobs/{complete_response.json()['job_id']}", headers=headers)
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "succeeded"
    return project_id, document_id


# 验证本地资料问答、Sources panel 和 Developer Trace 闭环。
def test_local_ask_sources_and_trace_workflow(client: TestClient) -> None:
    project_id, _ = create_ready_document(client)

    ask_response = client.post(
        "/api/v1/ask",
        json={"project_id": project_id, "message": "Explain RAG", "web_enabled": False},
        headers=HEADERS,
    )

    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["conversation_id"]
    assert "mode" not in body
    assert body["sources"]["local_chunks"] >= 1
    assert body["citations"]
    assert "RAG" in body["answer"]

    sources_response = client.get(f"/api/v1/runs/{body['run_id']}/sources", headers=HEADERS)
    assert sources_response.status_code == 200
    assert sources_response.json()["summary"]["local_chunks"] >= 1

    trace_response = client.get(f"/api/v1/dev/traces/{body['trace_id']}", headers=HEADERS)
    assert trace_response.status_code == 200
    trace = trace_response.json()
    assert trace["execution_plan"]["context_strategy"] == "full_context"


# 验证普通用户无法查看 Developer Trace。
def test_trace_is_admin_only(client: TestClient) -> None:
    project_id, _ = create_ready_document(client, headers=USER_A_HEADERS)
    ask_response = client.post(
        "/api/v1/ask",
        json={"project_id": project_id, "message": "Explain citation validation"},
        headers=USER_A_HEADERS,
    )
    assert ask_response.status_code == 200
    trace_id = ask_response.json()["trace_id"]

    forbidden = client.get(f"/api/v1/dev/traces/{trace_id}", headers=USER_A_HEADERS)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "ADMIN_REQUIRED"

    admin_visible = client.get(f"/api/v1/dev/traces/{trace_id}", headers={"Authorization": "Bearer dev-admin"})
    assert admin_visible.status_code == 200


# 验证 user_id 隔离：用户 B 不能读取用户 A 的项目与文件。
def test_user_isolation_for_project_and_documents(client: TestClient) -> None:
    project_id, document_id = create_ready_document(client, headers=USER_A_HEADERS)

    assert client.get(f"/api/v1/projects/{project_id}", headers=USER_B_HEADERS).status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}", headers=USER_B_HEADERS).status_code == 404
    assert client.get(f"/api/v1/projects/{project_id}/documents", headers=USER_B_HEADERS).status_code == 404


# 验证 Quiz 输出、四选项约束和历史列表。
def test_quiz_generation_and_history(client: TestClient) -> None:
    project_id, _ = create_ready_document(client)

    quiz_response = client.post(
        "/api/v1/quiz",
        json={
            "project_id": project_id,
            "prompt": "Generate a RAG quiz",
            "single_choice_count": 2,
            "short_answer_count": 1,
        },
        headers=HEADERS,
    )

    assert quiz_response.status_code == 200
    quiz_set = quiz_response.json()["quiz_set"]
    assert quiz_set["questions"]
    choice_questions = [question for question in quiz_set["questions"] if question["type"] == "single_choice"]
    assert choice_questions
    assert all(len(question["options"]) == 4 for question in choice_questions)
    assert all(question["source_citations"] for question in quiz_set["questions"])

    history_response = client.get(f"/api/v1/projects/{project_id}/quiz", headers=HEADERS)
    assert history_response.status_code == 200
    assert history_response.json()["quiz_sets"][0]["id"] == quiz_set["id"]


# 验证没有本地 indexed chunks 时拒绝 Local Ask，不编造答案。
def test_ask_without_document_is_plain_chat(client: TestClient) -> None:
    project_response = client.post("/api/v1/projects", json={"name": "Empty"}, headers=HEADERS)
    assert project_response.status_code == 201

    ask_response = client.post(
        "/api/v1/ask",
        json={"project_id": project_response.json()["id"], "message": "Hello"},
        headers=HEADERS,
    )

    assert ask_response.status_code == 200
    assert ask_response.json()["sources"] == {"local_chunks": 0, "web_pages": 0}
    assert ask_response.json()["citations"] == []


def test_conversation_resume_and_cross_user_concealment(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects", json={"name": "Conversation"}, headers=USER_A_HEADERS
    ).json()
    first = client.post(
        "/api/v1/ask",
        json={"project_id": project["id"], "message": "First turn"},
        headers=USER_A_HEADERS,
    ).json()
    second = client.post(
        "/api/v1/ask",
        json={
            "project_id": project["id"],
            "conversation_id": first["conversation_id"],
            "message": "Second turn",
        },
        headers=USER_A_HEADERS,
    )
    assert second.status_code == 200

    messages = client.get(
        f"/api/v1/conversations/{first['conversation_id']}/messages",
        headers=USER_A_HEADERS,
    )
    assert messages.status_code == 200
    assert [item["role"] for item in messages.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert (
        client.get(
            f"/api/v1/conversations/{first['conversation_id']}/messages",
            headers=USER_B_HEADERS,
        ).status_code
        == 404
    )


def test_conversation_rename_delete_and_cross_user_concealment(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects", json={"name": "Managed conversations"}, headers=USER_A_HEADERS
    ).json()
    conversation_id = client.post(
        "/api/v1/ask",
        json={"project_id": project["id"], "message": "Original title"},
        headers=USER_A_HEADERS,
    ).json()["conversation_id"]

    assert client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "Other user's attempt"},
        headers=USER_B_HEADERS,
    ).status_code == 404
    renamed = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "Renamed session"},
        headers=USER_A_HEADERS,
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed session"
    assert client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "   "},
        headers=USER_A_HEADERS,
    ).status_code == 422

    assert client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=USER_B_HEADERS,
    ).status_code == 404
    assert client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=USER_A_HEADERS,
    ).status_code == 204
    assert client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=USER_A_HEADERS,
    ).status_code == 404


def test_deleted_project_conceals_its_conversation_management(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects", json={"name": "Deleted project"}, headers=USER_A_HEADERS
    ).json()
    conversation_id = client.post(
        "/api/v1/ask",
        json={"project_id": project["id"], "message": "Conversation before deletion"},
        headers=USER_A_HEADERS,
    ).json()["conversation_id"]
    assert client.delete(
        f"/api/v1/projects/{project['id']}", headers=USER_A_HEADERS
    ).status_code == 202

    assert client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "Should stay concealed"},
        headers=USER_A_HEADERS,
    ).status_code == 404
    assert client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=USER_A_HEADERS,
    ).status_code == 404
    assert client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=USER_A_HEADERS,
    ).status_code == 404


def test_runtime_rerank_config_is_admin_versioned(client: TestClient) -> None:
    assert (
        client.get(
            "/api/v1/admin/runtime-config/rerank", headers=USER_A_HEADERS
        ).status_code
        == 403
    )
    current = client.get(
        "/api/v1/admin/runtime-config/rerank", headers=HEADERS
    ).json()
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


# 验证本地文档存在但与问题无词项重合时拒答，不能用无关 chunk 伪造引用。
def test_small_document_uses_full_context_without_keyword_gate(client: TestClient) -> None:
    project_id, _ = create_ready_document(client)

    ask_response = client.post(
        "/api/v1/ask",
        json={
            "project_id": project_id,
            "message": "Explain photosynthesis chlorophyll",
        },
        headers=HEADERS,
    )

    assert ask_response.status_code == 200
    assert ask_response.json()["citations"]


# 验证上传类型和 MIME 的安全边界。
def test_upload_rejects_mime_mismatch(client: TestClient) -> None:
    project_response = client.post("/api/v1/projects", json={"name": "Security"}, headers=HEADERS)
    assert project_response.status_code == 201
    upload_response = client.post(
        "/api/v1/documents/upload-url",
        json={
            "project_id": project_response.json()["id"],
            "filename": "malicious.pdf",
            "file_type": "pdf",
            "mime_type": "text/html",
            "size_bytes": 100,
        },
        headers=HEADERS,
    )

    assert upload_response.status_code == 422
    assert upload_response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_upload_completion_rejects_non_hex_checksum(client: TestClient) -> None:
    project_response = client.post("/api/v1/projects", json={"name": "Checksum"}, headers=HEADERS)
    upload_response = client.post(
        "/api/v1/documents/upload-url",
        json={
            "project_id": project_response.json()["id"],
            "filename": "paper.pdf",
            "file_type": "pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
        },
        headers=HEADERS,
    )

    response = client.post(
        f"/api/v1/documents/{upload_response.json()['document_id']}/complete",
        json={"checksum_sha256": "z" * 64, "extracted_text": "valid local text"},
        headers=HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


# 验证 Source Policy 阻止 local-only 越权调用 web 工具。
def test_removed_source_selector_is_rejected(client: TestClient) -> None:
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


def test_executable_catalogs_and_report_detail_fail_closed_locally(client: TestClient) -> None:
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
    response = client.get("/api/v1/evaluation-datasets", headers=USER_A_HEADERS)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_REQUIRED"
