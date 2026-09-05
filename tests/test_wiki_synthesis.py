"""Verify semantic synthesis uses all sections and rejects malformed provider output."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from researchmate_api.services.llm import LLMResult
from researchmate_api.services.retrieval import estimate_tokens
from researchmate_api.services.wiki_synthesis import SYNTHESIS_INPUT_TOKENS, synthesize_narrative


def test_synthesis_uses_every_section_and_returns_provider_narrative() -> None:
    inputs: list[list[str]] = []

    def complete(messages: list[dict[str, str]]) -> LLMResult:
        inputs.append(json.loads(messages[-1]["content"]))
        return LLMResult(
            content=json.dumps(
                {"summary": "A explains B under C.", "argument_flow": ["A", "B", "C"]}
            ),
            reasoning=None,
            model="fixture",
            prompt_tokens=0,
            completion_tokens=0,
        )

    result = synthesize_narrative(["Premise A", "Result B", "Condition C"], complete)

    assert inputs == [["Premise A", "Result B", "Condition C"]]
    assert result.summary == "A explains B under C."
    assert result.argument_flow == ["A", "B", "C"]


def test_synthesis_rejects_invalid_output_without_partial_success() -> None:
    def complete(messages: list[dict[str, str]]) -> LLMResult:
        return LLMResult("{}", None, "fixture", 0, 0)

    with pytest.raises(ValidationError):
        synthesize_narrative(["Evidence"], complete)


def test_hierarchical_synthesis_counts_full_prompt_and_covers_long_input() -> None:
    prompts: list[list[dict[str, str]]] = []

    def complete(messages: list[dict[str, str]]) -> LLMResult:
        prompts.append(messages)
        return LLMResult(
            '{"summary":"Integrated result","argument_flow":[]}', None, "fixture", 0, 0
        )

    synthesize_narrative(["甲" * 5990], complete)

    assert len(prompts) >= 3
    assert all(
        estimate_tokens(json.dumps(prompt, ensure_ascii=False)) <= SYNTHESIS_INPUT_TOKENS
        for prompt in prompts
    )
    leaves = [json.loads(prompt[-1]["content"]) for prompt in prompts[:-1]]
    assert sum(part.count("甲") for batch in leaves for part in batch) == 5990
