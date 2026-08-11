"""Verify owner-scoped answer feedback and immutable Bad Case promotion."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from researchmate_api.persistence.evidence_feedback import _normalize_feedback_evidence
from researchmate_api.schemas.common import SourceType

from tests.api_workflow_support import HEADERS, USER_A_HEADERS, create_ready_document

pytest_plugins = ["tests.api_workflow_fixtures"]


def _grounded_answer(client: TestClient) -> tuple[str, dict[str, object]]:
    project_id, _ = create_ready_document(client)
    response = client.post(
        "/api/v1/ask",
        json={"project_id": project_id, "message": "What does RAG mean?"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    return project_id, response.json()


def test_user_can_rate_owned_answer_and_reload_feedback_state(client: TestClient) -> None:
    """Persist one rating per owned Ask run and expose it with conversation history."""
    _project_id, answer = _grounded_answer(client)

    created = client.put(
        f"/api/v1/answer-feedback/{answer['run_id']}",
        json={
            "rating": "not_helpful",
            "category": "missing_context",
            "comment": "The answer omitted the retrieval step.",
        },
        headers=HEADERS,
    )

    assert created.status_code == 200
    feedback = created.json()
    assert feedback["ask_run_id"] == answer["run_id"]
    assert feedback["rating"] == "not_helpful"
    assert feedback["status"] == "new"
    assert (
        client.put(
            f"/api/v1/answer-feedback/{answer['run_id']}",
            json={"rating": "helpful", "category": None, "comment": None},
            headers=USER_A_HEADERS,
        ).status_code
        == 404
    )

    history = client.get(
        f"/api/v1/conversations/{answer['conversation_id']}/messages", headers=HEADERS
    ).json()["messages"]
    assistant = next(message for message in history if message["role"] == "assistant")
    assert assistant["ask_run_id"] == answer["run_id"]
    assert assistant["feedback_rating"] == "not_helpful"


def test_developer_promotes_reviewed_feedback_to_new_frozen_dataset_version(
    client: TestClient,
) -> None:
    """Create an immutable regression-set version from explicit reviewed evidence."""
    project_id, answer = _grounded_answer(client)
    created = client.put(
        f"/api/v1/answer-feedback/{answer['run_id']}",
        json={"rating": "not_helpful", "category": "incorrect_citation"},
        headers=HEADERS,
    ).json()
    feedback_list = client.get(
        f"/api/v1/projects/{project_id}/answer-feedback?rating=not_helpful",
        headers=HEADERS,
    )
    assert feedback_list.status_code == 200
    assert feedback_list.json()["items"][0]["feedback_id"] == created["feedback_id"]
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/answer-feedback", headers=USER_A_HEADERS
        ).status_code
        == 403
    )

    expected_chunk_ids = created["citation_chunk_ids"]
    assert expected_chunk_ids
    promoted = client.post(
        f"/api/v1/answer-feedback/{created['feedback_id']}/promote",
        json={"expected_chunk_ids": expected_chunk_ids},
        headers=HEADERS,
    )

    assert promoted.status_code == 201
    result = promoted.json()
    assert result["dataset_version"] == 1
    assert result["dataset_status"] == "frozen"
    assert (
        client.post(
            f"/api/v1/answer-feedback/{created['feedback_id']}/promote",
            json={"expected_chunk_ids": expected_chunk_ids},
            headers=HEADERS,
        ).status_code
        == 409
    )


def test_promotion_rejects_helpful_feedback_and_duplicate_evidence(
    client: TestClient,
) -> None:
    """Require a reviewed negative case and one judgment per retrieved chunk."""
    _project_id, answer = _grounded_answer(client)
    created = client.put(
        f"/api/v1/answer-feedback/{answer['run_id']}",
        json={"rating": "helpful"},
        headers=HEADERS,
    ).json()
    chunk_id = created["citation_chunk_ids"][0]

    helpful = client.post(
        f"/api/v1/answer-feedback/{created['feedback_id']}/promote",
        json={"expected_chunk_ids": [chunk_id]},
        headers=HEADERS,
    )
    duplicate = client.post(
        f"/api/v1/answer-feedback/{created['feedback_id']}/promote",
        json={"expected_chunk_ids": [chunk_id, chunk_id]},
        headers=HEADERS,
    )

    assert helpful.status_code == 409
    assert helpful.json()["error"]["code"] == "FEEDBACK_NOT_BAD_CASE"
    assert duplicate.status_code == 422


def test_promotion_rejects_evidence_that_was_not_retrieved(client: TestClient) -> None:
    """Prevent a reviewer request from forging relevance evidence outside the Ask trace."""
    _project_id, answer = _grounded_answer(client)
    created = client.put(
        f"/api/v1/answer-feedback/{answer['run_id']}",
        json={"rating": "not_helpful", "category": "missing_context"},
        headers=HEADERS,
    ).json()

    response = client.post(
        f"/api/v1/answer-feedback/{created['feedback_id']}/promote",
        json={"expected_chunk_ids": [str(uuid4())]},
        headers=HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EXPECTED_EVIDENCE_INVALID"


def test_promotion_rejects_retrieved_web_evidence_that_evaluator_cannot_replay(
    client: TestClient,
) -> None:
    """Keep local-document regression sets executable by the current evaluation adapter."""
    _project_id, answer = _grounded_answer(client)
    created = client.put(
        f"/api/v1/answer-feedback/{answer['run_id']}",
        json={"rating": "not_helpful", "category": "incorrect_citation"},
        headers=HEADERS,
    ).json()
    repository = client.app.state.evidence_store
    key = next(key for key in repository.answer_feedback if str(key[1]) == answer["run_id"])
    record = repository.answer_feedback[key]
    repository.answer_feedback[key] = record.model_copy(
        update={
            "retrieved_evidence": [
                evidence.model_copy(update={"source_type": SourceType.WEB_PAGE})
                for evidence in record.retrieved_evidence
            ]
        }
    )

    response = client.post(
        f"/api/v1/answer-feedback/{created['feedback_id']}/promote",
        json={"expected_chunk_ids": created["citation_chunk_ids"]},
        headers=HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EXPECTED_EVIDENCE_INVALID"


def test_legacy_retrieval_trace_infers_replayable_source_type() -> None:
    """Keep feedback on pre-migration Ask traces compatible after provenance hardening."""
    local_id, web_id = uuid4(), uuid4()

    normalized = _normalize_feedback_evidence(
        [
            {"chunk_id": str(local_id), "document_id": str(uuid4())},
            {"chunk_id": str(web_id), "document_id": None},
        ]
    )

    assert [item.source_type for item in normalized] == [
        SourceType.LOCAL_DOC,
        SourceType.WEB_PAGE,
    ]
