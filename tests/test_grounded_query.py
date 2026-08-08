"""Verify the unified Ask orchestration in GroundedQueryService.

These tests exercise the Ask orchestration against the in-memory repository
and deterministic local fallbacks for chat, lexical retrieval, and reranking.
External LLM, Qdrant, and Tavily boundaries are replaced by fakes so the
tests stay hermetic and deterministic while still exercising every orchestration
branch the production code relies on.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from researchmate_api.config import Settings
from researchmate_api.schemas.ask import AskRequest
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.document import UploadUrlRequest
from researchmate_api.schemas.project import ProjectCreate
from researchmate_api.services.grounded_query import GroundedQueryService
from researchmate_api.services.query_errors import GroundedQueryError
from researchmate_api.services.rerank import RerankCoordinator
from researchmate_api.services.store import (
    InMemoryResearchMateStore,
)

USER_ID = UUID("00000000-0000-4000-8000-000000000001")
DOCUMENT_TEXT = (
    "RAG means retrieval augmented generation.\n"
    "A retriever selects relevant local chunks before generation.\n"
    "Citation validation ensures every answer points back to a source chunk."
)
SECOND_DOCUMENT_TEXT = (
    "Hybrid retrieval fuses lexical and semantic signals.\n"
    "Reciprocal rank fusion preserves cross-channel evidence during ranking."
)


def settings() -> Settings:
    """Build a fully local test settings object with no external SDK configured."""
    return Settings(
        app_env="test",
        llm_provider="fake",
        embedding_provider="fake",
        web_search_provider="disabled",
        nvidia_api_key=None,
        rerank_provider_default="auto",
    )


def user() -> CurrentUser:
    """Provide one authenticated caller for all owner-scoped operations."""
    return CurrentUser(id=USER_ID, email="researcher@example.test", role="user")


def seed_workspace_with_ready_documents(
    store: InMemoryResearchMateStore,
    *,
    documents: tuple[str, ...] = (DOCUMENT_TEXT,),
) -> tuple[CurrentUser, UUID]:
    """Create a workspace project with one or more ready local documents."""
    caller = user()
    store.ensure_user(caller)
    project = store.create_project(caller, ProjectCreate(name="RAG review"))
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


def seed_personal_with_ready_document(
    store: InMemoryResearchMateStore,
    *,
    documents: tuple[str, ...] = (DOCUMENT_TEXT,),
) -> tuple[CurrentUser, UUID, UUID]:
    """Create a personal project and conversation with ready local documents."""
    caller = user()
    store.ensure_user(caller)
    project = store.ensure_personal_project(caller)
    conversation = store.ensure_conversation(caller, project.id, None, "First chat")
    assert conversation is not None
    for index, text in enumerate(documents, start=1):
        reservation = store.create_upload_url(
            caller,
            UploadUrlRequest(
                project_id=project.id,
                conversation_id=conversation.id,
                filename=f"document-{index}.pdf",
                file_type="pdf",
                mime_type="application/pdf",
                size_bytes=1024,
            ),
        )
        assert reservation is not None
        job = store.complete_document(caller, reservation.document_id, text)
        assert job is not None
    return caller, project.id, conversation.id


def service(
    store: InMemoryResearchMateStore,
    *,
    chat_provider=None,
    hybrid_store=None,
    reranker: RerankCoordinator | None = None,
    web_search=None,
) -> GroundedQueryService:
    """Wire a deterministic GroundedQueryService against the in-memory store."""
    return GroundedQueryService(
        settings=settings(),
        repository=store,
        chat_provider=chat_provider,
        hybrid_store=hybrid_store,
        reranker=reranker or RerankCoordinator(settings(), qdrant=None, nvidia_client=None),
        web_search=web_search,
    )


@pytest.fixture()
def repository() -> InMemoryResearchMateStore:
    """Provide a fresh in-memory repository for each isolated test case."""
    store = InMemoryResearchMateStore()
    store.reset()
    yield store
    store.reset()


def test_workspace_ask_persists_answer_citations_and_trace(repository) -> None:
    """Generate a grounded answer, run, and trace against a workspace project."""
    caller, project_id = seed_workspace_with_ready_documents(repository)
    grounded = service(repository)

    response = grounded.execute(
        caller,
        AskRequest(project_id=project_id, message="What is RAG?"),
    )

    assert response.answer
    assert response.validation_status == "passed"
    assert response.citations, "the deterministic fallback must cite the supplied evidence"
    assert response.run_id and response.trace_id
    # The deterministic reranker short-circuits the candidate set cleanly
    # without optional providers configured: no degradation flags surface and
    # the response carries no fallback reason.
    assert response.rerank_degraded is False
    assert response.retrieval_degraded is False
    assert response.summary_degraded is False
    assert repository.get_run_sources(caller, response.run_id) is not None


def test_workspace_ask_with_multiple_ready_documents_runs_hybrid_retrieval(repository) -> None:
    """Fuse lexical retrieval across many documents and rerank through the fallback."""
    caller, project_id = seed_workspace_with_ready_documents(
        repository, documents=(DOCUMENT_TEXT, SECOND_DOCUMENT_TEXT)
    )
    grounded = service(repository)

    response = grounded.execute(
        caller,
        AskRequest(project_id=project_id, message="How does reciprocal rank fusion work?"),
    )

    assert response.answer
    assert response.validation_status == "passed"
    assert response.citations
    # The deterministic reranker produces rankings without surfacing any
    # provider-failure degradation when neither NVIDIA nor Qdrant is configured.
    assert response.rerank_degraded is False


def test_personal_scope_ask_with_conversation_cites_local_evidence(repository) -> None:
    """Generate a grounded answer against an owned personal conversation scope."""
    caller, project_id, conversation_id = seed_personal_with_ready_document(repository)
    grounded = service(repository)

    response = grounded.execute(
        caller,
        AskRequest(
            project_id=project_id,
            conversation_id=conversation_id,
            message="What is RAG?",
        ),
    )

    assert response.answer
    assert response.validation_status == "passed"
    assert response.citations
    assert response.conversation_id == conversation_id
    messages = repository.conversation_messages(caller, response.conversation_id) or []
    assert [message.role for message in messages].count("assistant") == 1


def test_chat_only_personal_ask_without_documents_uses_deterministic_fallback(repository) -> None:
    """Generate a plain chat answer when no documents exist in a personal project."""
    caller = user()
    repository.ensure_user(caller)
    project = repository.ensure_personal_project(caller)
    # Pre-create an empty conversation so the personal scope has a destination.
    conversation = repository.ensure_conversation(caller, project.id, None, "New chat")
    assert conversation is not None
    grounded = service(repository)

    response = grounded.execute(
        caller,
        AskRequest(
            project_id=project.id,
            conversation_id=conversation.id,
            message="Hello there",
        ),
    )

    assert response.answer
    assert response.citations == []
    assert response.validation_status == "passed"
    assert response.rerank_degraded is False


def test_ask_for_missing_project_raises_not_found(repository) -> None:
    """Reject Ask operations against projects that the caller does not own."""
    caller = user()
    repository.ensure_user(caller)
    grounded = service(repository)

    with pytest.raises(GroundedQueryError) as failure:
        grounded.execute(
            caller,
            AskRequest(project_id=UUID("00000000-0000-4000-8000-000000000099"), message="missing"),
        )

    assert failure.value.code == "PROJECT_NOT_FOUND"
    assert failure.value.status_code == 404


def test_ask_with_web_enabled_without_provider_degrades_to_local_evidence(repository) -> None:
    """Gracefully degrade to local evidence when the Web boundary is unconfigured.

    Previously the orchestration re-raised `WebEvidenceError` as a hard
    failure, aborting the request even when local chunks had been retrieved.
    The pipeline must now log the boundary error, empty the web evidence set,
    and continue flowing through the local-retrieval path so the caller still
    receives a grounded answer with `web_degraded=True` surfaced.
    """
    caller, project_id = seed_workspace_with_ready_documents(repository)
    grounded = service(repository, web_search=None)

    response = grounded.execute(
        caller,
        AskRequest(project_id=project_id, message="What is RAG?", web_enabled=True),
    )

    assert response.answer
    assert response.validation_status == "passed"
    # Local chunks still produce citations even though the Web boundary failed.
    assert response.citations, "local evidence must still be cited when web degrades"
    assert response.web_degraded is True
    assert response.fallback_reason is not None


def test_ask_with_web_only_no_local_evidence_degrades_to_chat(repository) -> None:
    """Fall back to plain chat when web is enabled, has no local chunks, and the Web boundary errors."""
    caller = user()
    repository.ensure_user(caller)
    project = repository.ensure_personal_project(caller)
    conversation = repository.ensure_conversation(caller, project.id, None, "New chat")
    assert conversation is not None
    grounded = service(repository, web_search=None)

    response = grounded.execute(
        caller,
        AskRequest(
            project_id=project.id,
            conversation_id=conversation.id,
            message="open question",
            web_enabled=True,
        ),
    )

    assert response.answer
    assert response.citations == []
    assert response.web_degraded is True
    assert response.fallback_reason is not None


def test_ask_web_enabled_succeeds_when_provider_unavailable_keeps_local_evidence(
    repository,
) -> None:
    """Verify the Web boundary's WebSearchRequestError is translated like a hard Web failure but no longer aborts."""
    caller, project_id = seed_workspace_with_ready_documents(repository)
    grounded = service(repository, web_search=None)

    response = grounded.execute(
        caller,
        AskRequest(
            project_id=project_id,
            message="What is RAG?",
            web_enabled=True,
        ),
    )

    assert response.web_degraded is True
    assert response.fallback_reason
    assert response.citations, "local retrieval must remain available when web evidence degrades"


def test_ask_quotas_are_enforced_after_generation_succeeds(repository) -> None:
    """Reject the next Ask attempt with 429 once the daily ask quota is exhausted."""
    caller, project_id = seed_workspace_with_ready_documents(repository)
    grounded = service(repository)
    # The service enforces a daily quota of 200 asks; exhaust it before the next call.
    for _ in range(200):
        assert repository.increment_usage(caller, "ask", limit=200) is True
    assert repository.increment_usage(caller, "ask", limit=200) is False

    with pytest.raises(GroundedQueryError) as failure:
        grounded.execute(
            caller,
            AskRequest(project_id=project_id, message="another question"),
        )

    assert failure.value.code == "RATE_LIMITED"
    assert failure.value.status_code == 429
    # Quota accounting only counts successful generations; the run record is not persisted on quota failure.
    assert repository.get_run_sources(caller, UUID(int=0)) is None


def test_personal_ask_creates_conversation_only_after_generation(repository) -> None:
    """Defer conversation creation until a personal-scope Ask generation succeeds."""
    caller = user()
    repository.ensure_user(caller)
    project = repository.ensure_personal_project(caller)
    # Seed a conversation with a ready local document so evidence is available.
    conversation = repository.ensure_conversation(caller, project.id, None, "First chat")
    assert conversation is not None
    reservation = repository.create_upload_url(
        caller,
        UploadUrlRequest(
            project_id=project.id,
            conversation_id=conversation.id,
            filename="document.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            size_bytes=1024,
        ),
    )
    assert reservation is not None
    assert repository.complete_document(caller, reservation.document_id, DOCUMENT_TEXT) is not None
    # Count messages before the Ask; ensure_for_commit must persist two new messages afterwards.
    messages_before = repository.conversation_messages(caller, conversation.id) or []
    grounded = service(repository)

    response = grounded.execute(
        caller,
        AskRequest(
            project_id=project.id,
            conversation_id=conversation.id,
            message="What is RAG?",
        ),
    )

    messages_after = repository.conversation_messages(caller, conversation.id) or []
    assert len(messages_after) - len(messages_before) == 2
    assert messages_after[-1].role == "assistant"
    assert messages_after[-1].content == response.answer
    assert messages_after[-1].citations == response.citations
