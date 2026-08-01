"""Generate a bounded answer from selected evidence or an honest no-evidence state."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from researchmate_api.schemas.common import SourceSummary
from researchmate_api.schemas.conversation import ConversationMessage
from researchmate_api.services.answering import (
    ProviderOutputError,
    build_chat_answer,
    build_grounded_answer,
    build_llm_chat_answer,
    build_llm_grounded_answer,
)
from researchmate_api.services.llm import ChatProvider, LLMResult, ProviderRequestError
from researchmate_api.services.store import ChunkEntry


class AnswerGenerationError(RuntimeError):
    """Carry a stable generation failure without coupling to HTTP."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        """Record the public failure contract for the interface mapper."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class GenerationOutcome:
    """Return generated content, evidence metadata, usage, and elapsed time."""

    answer: str
    citations: list
    summary: SourceSummary
    provider_result: LLMResult | None
    latency_ms: int


def generate_answer(
    provider: ChatProvider | None,
    query: str,
    retrieved: list[ChunkEntry],
    history: list[ConversationMessage],
    *,
    documents_present: bool,
    web_enabled: bool,
    max_output_tokens: int,
) -> GenerationOutcome:
    """Generate from evidence, abstain on irrelevant documents, or use plain chat."""
    started = monotonic()
    llm_result = None
    try:
        if retrieved:
            if provider is not None:
                answer, citations, summary, llm_result = build_llm_grounded_answer(
                    provider, query, retrieved, history, max_output_tokens
                )
            else:
                answer, citations, summary = build_grounded_answer(query, retrieved)
        elif documents_present and not web_enabled:
            answer = (
                "当前资料中没有与这个问题足够相关的依据。请换一种问法、补充资料，"
                "或在允许时启用 Web 搜索。"
            )
            citations = []
            summary = SourceSummary()
        else:
            if provider is not None:
                answer, llm_result = build_llm_chat_answer(
                    provider, query, history, max_output_tokens
                )
            else:
                answer = build_chat_answer(query)
            citations = []
            summary = SourceSummary()
    except ProviderOutputError as exc:
        raise AnswerGenerationError(
            "LLM_OUTPUT_INVALID",
            "The model response failed grounded-output validation.",
            502,
        ) from exc
    except ProviderRequestError as exc:
        raise AnswerGenerationError(
            "LLM_UNAVAILABLE",
            "The model provider is temporarily unavailable.",
            503,
        ) from exc
    return GenerationOutcome(
        answer=answer,
        citations=citations,
        summary=summary,
        provider_result=llm_result,
        latency_ms=round((monotonic() - started) * 1000),
    )
