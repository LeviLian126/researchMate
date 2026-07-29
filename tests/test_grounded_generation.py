import json
from uuid import UUID

import pytest
from researchmate_api.schemas.common import SourceType
from researchmate_api.services.answering import (
    ProviderOutputError,
    build_llm_grounded_answer,
)
from researchmate_api.services.llm import LLMResult
from researchmate_api.services.quiz_generation import generate_llm_quiz_set
from researchmate_api.services.store import ChunkEntry


class FakeProvider:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.messages: list[dict[str, str]] = []

    def complete(self, messages):
        self.messages = list(messages)
        return LLMResult(
            content=json.dumps(self.payload),
            reasoning=None,
            model="fake",
            prompt_tokens=10,
            completion_tokens=5,
        )


class SequenceFakeProvider:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages):
        self.calls.append(list(messages))
        return LLMResult(
            content=json.dumps(self.payloads.pop(0)),
            reasoning=None,
            model="fake",
            prompt_tokens=10,
            completion_tokens=5,
        )


def evidence_chunk(text: str) -> ChunkEntry:
    return ChunkEntry(
        id=UUID("10000000-0000-4000-8000-000000000001"),
        user_id=UUID("20000000-0000-4000-8000-000000000001"),
        project_id=UUID("30000000-0000-4000-8000-000000000001"),
        document_id=UUID("40000000-0000-4000-8000-000000000001"),
        source_type=SourceType.LOCAL_DOC,
        source_title="paper.pdf",
        text=text,
        page_no=7,
    )


def web_evidence_chunk(text: str) -> ChunkEntry:
    return ChunkEntry(
        id=UUID("60000000-0000-4000-8000-000000000001"),
        user_id=UUID("20000000-0000-4000-8000-000000000001"),
        project_id=UUID("30000000-0000-4000-8000-000000000001"),
        document_id=None,
        source_type=SourceType.WEB_PAGE,
        source_title="Official documentation",
        text=text,
        url="https://example.test/docs",
    )


def test_model_can_only_select_server_supplied_evidence() -> None:
    provider = FakeProvider(
        {"answer": "RAG retrieves evidence before generation.", "claims": [
            {"text": "Retrieval precedes generation.", "evidence_ids": [1]}
        ]}
    )

    answer, citations, summary, _result = build_llm_grounded_answer(
        provider,
        "What is RAG?",
        [evidence_chunk("RAG retrieves relevant passages before answer generation.")],
    )

    assert answer.startswith("RAG retrieves")
    assert len(citations) == 1
    assert citations[0].page_no == 7
    assert citations[0].claim_id == "claim_1"
    assert summary.local_chunks == 1
    assert "untrusted data" in provider.messages[0]["content"]


def test_quiz_provider_receives_user_instructions_and_server_evidence() -> None:
    provider = FakeProvider(
        {
            "questions": [
                {
                    "type": "single_choice",
                    "question": "Which statement is supported?",
                    "options": ["A", "B", "C", "D"],
                    "answer": "A",
                    "explanation": "The source supports A.",
                    "difficulty": "hard",
                    "evidence_ids": [1],
                }
            ]
        }
    )
    chunk = evidence_chunk("RAG retrieves evidence before generation.")
    from researchmate_api.services.answering import build_grounded_answer

    _, citations, _ = build_grounded_answer("quiz", [chunk])
    quiz, _ = generate_llm_quiz_set(
        provider,
        [chunk],
        citations,
        "Focus on retrieval and make it hard.",
        1,
        0,
        0,
    )
    assert quiz.questions[0].difficulty == "hard"
    assert quiz.questions[0].source_citations
    assert "Focus on retrieval" in provider.messages[1]["content"]


def test_grounded_answer_normalizes_database_source_type_strings() -> None:
    provider = FakeProvider(
        {
            "answer": "The stored document supports this answer.",
            "claims": [{"text": "The document supports it.", "evidence_ids": [1]}],
        }
    )
    chunk = evidence_chunk("Stored document evidence.")
    chunk.source_type = "local_doc"  # type: ignore[assignment]

    _answer, citations, summary, _result = build_llm_grounded_answer(
        provider,
        "Question",
        [chunk],
    )

    assert citations[0].source_type == SourceType.LOCAL_DOC
    assert citations[0].chunk_id == chunk.id
    assert summary.local_chunks == 1


def test_out_of_range_evidence_reference_is_rejected() -> None:
    provider = FakeProvider(
        {"answer": "Unsupported", "claims": [{"text": "Invented", "evidence_ids": [2]}]}
    )

    with pytest.raises(ProviderOutputError):
        build_llm_grounded_answer(
            provider,
            "Question",
            [evidence_chunk("Only evidence one exists")],
        )


def test_invalid_grounded_output_gets_one_bounded_repair_attempt() -> None:
    provider = SequenceFakeProvider([
        {"answer": "Missing claims"},
        {
            "answer": "The supplied evidence supports the answer.",
            "claims": [{"text": "Evidence supports it.", "evidence_ids": [1]}],
        },
    ])

    answer, citations, _summary, result = build_llm_grounded_answer(
        provider,
        "Question",
        [evidence_chunk("Evidence supports the answer.")],
    )

    assert answer.startswith("The supplied evidence")
    assert len(citations) == 1
    assert len(provider.calls) == 2
    assert "previous response was invalid" in provider.calls[1][-1]["content"]
    assert result.prompt_tokens == 20
    assert result.completion_tokens == 10


def test_web_citation_does_not_reference_an_ephemeral_chunk_row() -> None:
    provider = FakeProvider(
        {
            "answer": "The official documentation supports this answer.",
            "claims": [{"text": "Documentation supports it.", "evidence_ids": [1]}],
        }
    )

    _answer, citations, summary, _result = build_llm_grounded_answer(
        provider,
        "Question",
        [web_evidence_chunk("Official documentation evidence.")],
    )

    assert citations[0].chunk_id is None
    assert citations[0].url == "https://example.test/docs"
    assert summary.web_pages == 1
