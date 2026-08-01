"""Exercise core HTTP workflows for Ask, Quiz, projects, and conversations."""

from fastapi.testclient import TestClient

from tests.api_workflow_support import (
    HEADERS,
    USER_A_HEADERS,
    USER_B_HEADERS,
    create_ready_document,
)

pytest_plugins = ["tests.api_workflow_fixtures"]


# 验证本地资料问答、Sources panel 和 Developer Trace 闭环。
def test_local_ask_sources_and_trace_workflow(client: TestClient) -> None:
    """Persist an evidence-backed answer with sources and a developer trace."""
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
    assert trace["latency_ms"] == trace["token_usage"]["total_latency_ms"]
    assert trace["latency_ms"] >= 0
    assert all(call["latency_ms"] >= 0 for call in trace["tool_calls"])


# 验证普通用户无法查看 Developer Trace。
def test_trace_is_admin_only(client: TestClient) -> None:
    """Deny developer-trace access to a regular authenticated user."""
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

    admin_visible = client.get(
        f"/api/v1/dev/traces/{trace_id}", headers={"Authorization": "Bearer dev-admin"}
    )
    assert admin_visible.status_code == 200


# 验证 user_id 隔离：用户 B 不能读取用户 A 的项目与文件。
def test_user_isolation_for_project_and_documents(client: TestClient) -> None:
    """Conceal one user's project and document identifiers from another user."""
    project_id, document_id = create_ready_document(client, headers=USER_A_HEADERS)

    assert client.get(f"/api/v1/projects/{project_id}", headers=USER_B_HEADERS).status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}", headers=USER_B_HEADERS).status_code == 404
    assert (
        client.get(f"/api/v1/projects/{project_id}/documents", headers=USER_B_HEADERS).status_code
        == 404
    )


# 验证 Quiz 输出、四选项约束和历史列表。
def test_quiz_generation_and_history(client: TestClient) -> None:
    """Generate a contract-valid Quiz and expose it through project history."""
    project_id, _ = create_ready_document(client)

    quiz_response = client.post(
        "/api/v1/quiz",
        json={
            "project_id": project_id,
            "prompt": "Generate a RAG quiz",
            "single_choice_count": 2,
            "fill_blank_count": 1,
            "subjective_count": 1,
        },
        headers=HEADERS,
    )

    assert quiz_response.status_code == 200
    quiz_set = quiz_response.json()["quiz_set"]
    assert quiz_set["questions"]
    choice_questions = [
        question for question in quiz_set["questions"] if question["type"] == "single_choice"
    ]
    assert choice_questions
    assert all(len(question["options"]) == 4 for question in choice_questions)
    assert all(question["source_citations"] for question in quiz_set["questions"])
    assert {"single_choice", "fill_blank", "subjective"}.issubset(
        {question["type"] for question in quiz_set["questions"]}
    )

    history_response = client.get(f"/api/v1/projects/{project_id}/quiz", headers=HEADERS)
    assert history_response.status_code == 200
    assert history_response.json()["quiz_sets"][0]["id"] == quiz_set["id"]


def test_quiz_rejects_an_output_larger_than_the_response_contract(
    client: TestClient,
) -> None:
    """Reject a request whose question counts exceed the response boundary."""
    project_id, _ = create_ready_document(client)
    response = client.post(
        "/api/v1/quiz",
        json={
            "project_id": project_id,
            "single_choice_count": 20,
            "fill_blank_count": 20,
            "subjective_count": 20,
        },
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_personal_chat_attachments_are_conversation_scoped(client: TestClient) -> None:
    """Keep personal-project attachments isolated to their owning conversation."""
    personal = client.post("/api/v1/chat/bootstrap", headers=USER_A_HEADERS)
    assert personal.status_code == 200
    assert personal.json()["kind"] == "personal"
    project_id = personal.json()["id"]
    first = client.post(
        f"/api/v1/projects/{project_id}/conversations",
        json={"title": "First chat"},
        headers=USER_A_HEADERS,
    ).json()
    second = client.post(
        f"/api/v1/projects/{project_id}/conversations",
        json={"title": "Second chat"},
        headers=USER_A_HEADERS,
    ).json()

    upload = client.post(
        "/api/v1/documents/upload-url",
        json={
            "project_id": project_id,
            "conversation_id": first["id"],
            "filename": "private-notes.pdf",
            "file_type": "pdf",
            "mime_type": "application/pdf",
            "size_bytes": 128,
        },
        headers=USER_A_HEADERS,
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]
    completed = client.post(
        f"/api/v1/documents/{document_id}/complete",
        json={"extracted_text": "Conversation one contains the private keyword ALPHA-ONLY."},
        headers=USER_A_HEADERS,
    )
    assert completed.status_code == 202

    first_docs = client.get(
        f"/api/v1/conversations/{first['id']}/documents",
        headers=USER_A_HEADERS,
    )
    second_docs = client.get(
        f"/api/v1/conversations/{second['id']}/documents",
        headers=USER_A_HEADERS,
    )
    assert [item["id"] for item in first_docs.json()] == [document_id]
    assert second_docs.json() == []
    first_answer = client.post(
        "/api/v1/ask",
        json={
            "project_id": project_id,
            "conversation_id": first["id"],
            "message": "What is the private keyword?",
        },
        headers=USER_A_HEADERS,
    )
    second_answer = client.post(
        "/api/v1/ask",
        json={
            "project_id": project_id,
            "conversation_id": second["id"],
            "message": "What is the private keyword?",
        },
        headers=USER_A_HEADERS,
    )
    assert first_answer.json()["sources"]["local_chunks"] >= 1
    assert second_answer.json()["sources"]["local_chunks"] == 0


def test_personal_project_is_hidden_and_cannot_generate_quiz(client: TestClient) -> None:
    """Hide the personal project and deny project-wide Quiz generation on it."""
    first = client.post("/api/v1/chat/bootstrap", headers=USER_A_HEADERS).json()
    second = client.post("/api/v1/chat/bootstrap", headers=USER_A_HEADERS).json()
    assert first["id"] == second["id"]
    assert all(
        project["id"] != first["id"]
        for project in client.get("/api/v1/projects", headers=USER_A_HEADERS).json()
    )
    rejected = client.post(
        "/api/v1/quiz",
        json={"project_id": first["id"]},
        headers=USER_A_HEADERS,
    )
    assert rejected.status_code == 404
    assert rejected.json()["error"]["code"] == "QUIZ_NOT_AVAILABLE"


# 验证没有本地 indexed chunks 时拒绝 Local Ask，不编造答案。
def test_ask_without_document_is_plain_chat(client: TestClient) -> None:
    """Allow an empty workspace to answer as plain chat without fabricated sources."""
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
    """Resume an owned conversation while concealing it from another user."""
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
