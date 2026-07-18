import json
from uuid import UUID

import pytest

from researchmate_api.schemas.common import SourceMode, SourceType
from researchmate_api.services.answering import ProviderOutputError, build_llm_grounded_answer
from researchmate_api.services.llm import LLMResult
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


def test_model_can_only_select_server_supplied_evidence() -> None:
    provider = FakeProvider(
        {"answer": "RAG retrieves evidence before generation.", "claims": [
            {"text": "Retrieval precedes generation.", "evidence_ids": [1]}
        ]}
    )

    answer, citations, summary = build_llm_grounded_answer(
        provider,
        "What is RAG?",
        SourceMode.LOCAL_ONLY,
        [evidence_chunk("RAG retrieves relevant passages before answer generation.")],
    )

    assert answer.startswith("RAG retrieves")
    assert len(citations) == 1
    assert citations[0].page_no == 7
    assert citations[0].claim_id == "claim_1"
    assert summary.local_chunks == 1
    assert "untrusted data" in provider.messages[0]["content"]


def test_out_of_range_evidence_reference_is_rejected() -> None:
    provider = FakeProvider(
        {"answer": "Unsupported", "claims": [{"text": "Invented", "evidence_ids": [2]}]}
    )

    with pytest.raises(ProviderOutputError):
        build_llm_grounded_answer(
            provider,
            "Question",
            SourceMode.LOCAL_ONLY,
            [evidence_chunk("Only evidence one exists")],
        )
