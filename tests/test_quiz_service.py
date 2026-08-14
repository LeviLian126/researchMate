"""Verify QuizService resource scope, evidence binding, and quota enforcement.

These tests exercise the QuizService against the in-memory repository and
deterministic local quiz fallback. The optional LLM provider is replaced by
fakes that return either a valid schema-bound proposal or invalid output so
the service's error contract remains verifiable without network calls.
"""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.document import UploadUrlRequest
from researchmate_api.schemas.project import ProjectCreate
from researchmate_api.schemas.quiz import QuizRequest
from researchmate_api.services.llm import LLMResult
from researchmate_api.services.quiz_service import QuizService, QuizServiceError
from researchmate_api.services.store import InMemoryResearchMateStore

USER_ID = UUID("00000000-0000-4000-8000-000000000010")
DOCUMENT_TEXT = (
    "The retrieval pipeline orders candidate evidence via reciprocal rank fusion.\n"
    "Citations must reference identifiers that the server returned before generation.\n"
    "Quizzes bind every question to source-backed citations to avoid hallucinated claims."
)
SECOND_DOCUMENT_TEXT = (
    "RAG means retrieval augmented generation; evidence is selected first.\n"
    "Quizzes verify comprehension of the cited local evidence."
)


def user() -> CurrentUser:
    """Provide a stable authenticated caller for every owned quiz operation."""
    return CurrentUser(id=USER_ID, email="learner@example.test", role="user")


class StubProvider:
    """Return one deterministic LLM completion and record its prompt."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> LLMResult:
        self.calls.append(list(messages))
        return LLMResult(
            content=json.dumps(self.payload),
            reasoning=None,
            model="fake",
            prompt_tokens=10,
            completion_tokens=5,
        )


@pytest.fixture()
def repository() -> InMemoryResearchMateStore:
    """Provide a fresh in-memory repository for each isolated test case."""
    store = InMemoryResearchMateStore()
    store.reset()
    yield store
    store.reset()


def seed_workspace(
    store: InMemoryResearchMateStore,
    *,
    documents: tuple[str, ...] = (DOCUMENT_TEXT,),
    project_name: str = "RAG review",
) -> tuple[CurrentUser, UUID]:
    """Create a workspace project ready to receive a quiz request."""
    caller = user()
    store.ensure_user(caller)
    project = store.create_project(caller, ProjectCreate(name=project_name))
    for index, text in enumerate(documents, start=1):
        reservation = store.create_upload_url(
            caller,
            UploadUrlRequest(
                project_id=project.id,
                conversation_id=None,
                filename=f"document-{index}.pdf",
                file_type="pdf",
                mime_type="application/pdf",
                size_bytes=1024,
            ),
        )
        assert reservation is not None
        job = store.complete_document(caller, reservation.document_id, text)
        assert job is not None
    return caller, project.id


def valid_llm_payload(chunks: int, *, single_choice=1, fill_blank=0, subjective=0) -> dict:
    """Build a schema-valid provider quiz proposal for the supplied chunk count."""
    questions = []
    for index in range(single_choice):
        questions.append(
            {
                "type": "single_choice",
                "question": f"Single-choice question {index + 1}?",
                "options": ["alpha", "beta", "gamma", "delta"],
                "answer": "alpha",
                "explanation": "alpha is directly tied to the cited local evidence.",
                "difficulty": "medium",
                "evidence_ids": [1 + (index % max(1, chunks))],
            }
        )
    for index in range(fill_blank):
        questions.append(
            {
                "type": "fill_blank",
                "question": f"Fill the blank {index + 1}.",
                "answer": "cited evidence",
                "explanation": "fills the cited source.",
                "difficulty": "easy",
                "evidence_ids": [1 + (index % max(1, chunks))],
            }
        )
    for index in range(subjective):
        questions.append(
            {
                "type": "subjective",
                "question": f"Subjective prompt {index + 1}.",
                "answer": "discussed from evidence",
                "explanation": "must use the cited source.",
                "difficulty": "hard",
                "evidence_ids": [1 + (index % max(1, chunks))],
            }
        )
    return {"questions": questions}


def test_deterministic_quiz_returns_questions_and_coverage_for_workspace(repository) -> None:
    """Generate a deterministic, source-backed quiz from a workspace project."""
    caller, project_id = seed_workspace(repository)
    service = QuizService(repository=repository, chat_provider=None)

    response = service.create(
        caller,
        QuizRequest(
            project_id=project_id,
            prompt="Build a quiz from available evidence.",
            single_choice_count=1,
            fill_blank_count=0,
            subjective_count=0,
        ),
    )

    assert response.run_id
    assert response.trace_id
    assert response.validation_status == "passed"
    assert response.coverage.documents_available == 1
    assert response.coverage.documents_covered == 1
    assert response.coverage.chunks_selected >= 1
    questions = response.quiz_set.questions
    assert questions
    assert all(question.source_citations for question in questions)


def test_quiz_on_missing_project_raises_not_found(repository) -> None:
    """Reject Quiz requests against projects that do not exist."""
    caller = user()
    repository.ensure_user(caller)
    service = QuizService(repository=repository, chat_provider=None)

    with pytest.raises(QuizServiceError) as failure:
        service.create(
            caller,
            QuizRequest(
                project_id=UUID("00000000-0000-4000-8000-000000000199"),
                prompt="missing project",
            ),
        )

    assert failure.value.code == "PROJECT_NOT_FOUND"
    assert failure.value.status_code == 404


def test_quiz_on_personal_project_is_not_available(repository) -> None:
    """Reject Quiz requests against personal projects because quizzes require workspace scope."""
    caller = user()
    repository.ensure_user(caller)
    project = repository.ensure_personal_project(caller)
    service = QuizService(repository=repository, chat_provider=None)

    with pytest.raises(QuizServiceError) as failure:
        service.create(
            caller,
            QuizRequest(project_id=project.id, prompt="personal scope"),
        )

    assert failure.value.code == "QUIZ_NOT_AVAILABLE"
    assert failure.value.status_code == 404


def test_quiz_without_ready_documents_raises_document_not_indexed(repository) -> None:
    """Reject Quiz requests when the project has no ready local evidence."""
    caller = user()
    repository.ensure_user(caller)
    project = repository.create_project(caller, ProjectCreate(name="empty"))
    service = QuizService(repository=repository, chat_provider=None)

    with pytest.raises(QuizServiceError) as failure:
        service.create(
            caller,
            QuizRequest(project_id=project.id, prompt="no documents yet"),
        )

    assert failure.value.code == "DOCUMENT_NOT_INDEXED"
    assert failure.value.status_code == 409


def test_quiz_quota_enforced_after_successful_generation(repository) -> None:
    """Reject the next Quiz request with 429 once the daily quiz quota is exhausted."""
    caller, project_id = seed_workspace(repository)
    service = QuizService(repository=repository, chat_provider=None)
    # The service enforces a daily quota of 100 quizzes; exhaust it before the next call.
    for _ in range(100):
        assert repository.increment_usage(caller, "quiz", limit=100) is True
    assert repository.increment_usage(caller, "quiz", limit=100) is False

    with pytest.raises(QuizServiceError) as failure:
        service.create(
            caller,
            QuizRequest(project_id=project_id, prompt="exhausted quota"),
        )

    assert failure.value.code == "RATE_LIMITED"
    assert failure.value.status_code == 429


def test_topic_scope_uses_topic_query_for_chunk_ranking(repository) -> None:
    """Rank retrieved chunks by the supplied topic query in the topic scope."""
    caller, project_id = seed_workspace(repository, documents=(DOCUMENT_TEXT, SECOND_DOCUMENT_TEXT))
    service = QuizService(repository=repository, chat_provider=None)

    response = service.create(
        caller,
        QuizRequest(
            project_id=project_id,
            prompt="Drill comprehension of retrieval.",
            resource_scope="topic",
            topic_query="reciprocal rank fusion",
            single_choice_count=1,
            fill_blank_count=0,
            subjective_count=0,
        ),
    )
    assert response.coverage.chunks_selected <= 50
    questions = response.quiz_set.questions
    assert questions
    assert all(question.source_citations for question in questions)


def test_llm_provider_returns_typed_questions_matching_request(repository) -> None:
    """Pass request counts and evidence identifiers through the LLM quiz provider."""
    caller, project_id = seed_workspace(repository)
    provider = StubProvider(valid_llm_payload(chunks=1, single_choice=1))
    service = QuizService(repository=repository, chat_provider=provider)

    response = service.create(
        caller,
        QuizRequest(
            project_id=project_id,
            prompt="Focus on retrieval concepts.",
            single_choice_count=1,
            fill_blank_count=0,
            subjective_count=0,
        ),
    )
    questions = response.quiz_set.questions
    assert len(questions) == 1
    assert questions[0].type == "single_choice"
    assert questions[0].options == ["alpha", "beta", "gamma", "delta"]
    assert questions[0].source_citations, "the service must bind the LLM output to server citations"
    assert provider.calls, "the LLM provider must receive one completion request"
    assert "Focus on retrieval concepts." in provider.calls[0][1]["content"]
    assert "untrusted data" in provider.calls[0][0]["content"]


def test_llm_provider_invalid_output_raises_unavailable(repository) -> None:
    """Surface a 503 failure when the LLM quiz provider returns invalid output."""
    caller, project_id = seed_workspace(repository)
    invalid_payload = {"questions": []}
    provider = StubProvider(invalid_payload)
    service = QuizService(repository=repository, chat_provider=provider)

    with pytest.raises(QuizServiceError) as failure:
        service.create(
            caller,
            QuizRequest(project_id=project_id, prompt="invalid model response"),
        )

    assert failure.value.code == "QUIZ_PROVIDER_UNAVAILABLE"
    assert failure.value.status_code == 503


def test_select_chunks_all_ready_documents_covers_one_chunk_per_document(repository) -> None:
    """Cover at least one chunk per document in the all_ready_documents scope.

    Observes the chunk selection through the public QuizService.create method.
    The coverage field in the response reflects the _select_chunks output.
    """
    caller = user()
    repository.ensure_user(caller)
    project = repository.create_project(caller, ProjectCreate(name="multi-evidence"))
    texts = (DOCUMENT_TEXT, SECOND_DOCUMENT_TEXT)
    for index, text in enumerate(texts, start=1):
        reservation = repository.create_upload_url(
            caller,
            UploadUrlRequest(
                project_id=project.id,
                conversation_id=None,
                filename=f"document-{index}.pdf",
                file_type="pdf",
                mime_type="application/pdf",
                size_bytes=1024,
            ),
        )
        assert repository.complete_document(caller, reservation.document_id, text) is not None

    service = QuizService(repository=repository, chat_provider=None)
    response = service.create(
        caller,
        QuizRequest(
            project_id=project.id,
            prompt="multi-document quiz",
            single_choice_count=1,
        ),
    )

    assert response.coverage.documents_available == 2
    assert response.coverage.documents_covered == 2
    assert response.coverage.chunks_selected <= 50
    assert response.quiz_set.questions, "quiz must be generated with source-backed citations"
    assert all(question.source_citations for question in response.quiz_set.questions)


def test_invalid_quiz_request_question_total_raises_validation_error(repository) -> None:
    """QuizRequest validation rejects a question total outside the supported bounds."""
    caller, project_id = seed_workspace(repository)
    service = QuizService(repository=repository, chat_provider=None)

    with pytest.raises(ValueError):
        service.create(
            caller,
            QuizRequest(
                project_id=project_id,
                prompt="no questions requested",
                single_choice_count=0,
                fill_blank_count=0,
                subjective_count=0,
            ),
        )
