from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from researchmate_api.main import create_app
from researchmate_api.config import Settings
from researchmate_api.schemas.common import SourceMode, TaskType
from researchmate_api.services.source_policy import resolve_intent, validate_tool_policy
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
        json={"project_id": project_id, "message": "/study explain RAG", "selected_mode": "auto"},
        headers=HEADERS,
    )

    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["mode"] == "local_only"
    assert body["sources"]["local_chunks"] >= 1
    assert body["citations"]
    assert "RAG" in body["answer"]

    sources_response = client.get(f"/api/v1/runs/{body['run_id']}/sources", headers=HEADERS)
    assert sources_response.status_code == 200
    assert sources_response.json()["summary"]["local_chunks"] >= 1

    trace_response = client.get(f"/api/v1/dev/traces/{body['trace_id']}", headers=HEADERS)
    assert trace_response.status_code == 200
    trace = trace_response.json()
    assert trace["execution_plan"]["source_mode"] == "local_only"
    assert trace["validation_result"]["source_policy"]["denied_tools"] == []


# 验证普通用户无法查看 Developer Trace。
def test_trace_is_admin_only(client: TestClient) -> None:
    project_id, _ = create_ready_document(client, headers=USER_A_HEADERS)
    ask_response = client.post(
        "/api/v1/ask",
        json={"project_id": project_id, "message": "/study citation validation", "selected_mode": "auto"},
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
            "prompt": "/quiz RAG",
            "selected_mode": "local_only",
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
def test_local_ask_without_indexed_document_is_rejected(client: TestClient) -> None:
    project_response = client.post("/api/v1/projects", json={"name": "Empty"}, headers=HEADERS)
    assert project_response.status_code == 201

    ask_response = client.post(
        "/api/v1/ask",
        json={"project_id": project_response.json()["id"], "message": "/study nothing", "selected_mode": "auto"},
        headers=HEADERS,
    )

    assert ask_response.status_code == 409
    assert ask_response.json()["error"]["code"] == "DOCUMENT_NOT_INDEXED"


# 验证本地文档存在但与问题无词项重合时拒答，不能用无关 chunk 伪造引用。
def test_local_ask_rejects_unrelated_document_evidence(client: TestClient) -> None:
    project_id, _ = create_ready_document(client)

    ask_response = client.post(
        "/api/v1/ask",
        json={
            "project_id": project_id,
            "message": "/study explain photosynthesis chlorophyll",
            "selected_mode": "auto",
        },
        headers=HEADERS,
    )

    assert ask_response.status_code == 409
    assert ask_response.json()["error"]["code"] == "EVIDENCE_NOT_FOUND"


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
def test_source_policy_validator_blocks_unallowed_tools() -> None:
    intent = resolve_intent("/study explain retrieval", SourceMode.AUTO, TaskType.ANSWER)
    result = validate_tool_policy(intent.plan, ["query_local_docs", "search_web", "generate_answer"])

    assert intent.plan.source_mode == "local_only"
    assert result["passed"] is False
    assert result["denied_tools"] == ["search_web"]


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
