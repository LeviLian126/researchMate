from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from researchmate_api.schemas.evidence import SourceScope
from researchmate_api.services.llm import LLMResult
from researchmate_worker.budget import BudgetedChatProvider, WorkflowBudgetExceeded
from researchmate_worker.evaluation import PipelineRuntimeConfig


class _Result:
    def __init__(self, claimed: bool = True) -> None:
        self.claimed = claimed

    def one_or_none(self):
        return object() if self.claimed else None


class _Connection:
    def __init__(self, claimed: bool = True) -> None:
        self.claimed = claimed
        self.statements: list[str] = []

    def execute(self, statement, _parameters=None):
        source = str(statement).lower()
        self.statements.append(source)
        return _Result(self.claimed if "returning budget_reserved_usd" in source else True)


class _Engine:
    def __init__(self, claimed: bool = True) -> None:
        self.connection = _Connection(claimed)

    @contextmanager
    def begin(self):
        yield self.connection


class _Provider:
    def complete(self, messages):
        assert list(messages)
        return LLMResult(
            content="{}",
            reasoning=None,
            model="z-ai/glm-5.2",
            prompt_tokens=100,
            completion_tokens=20,
        )


def _budgeted(engine: _Engine, *, max_prompt_tokens: int = 1024) -> BudgetedChatProvider:
    provider = BudgetedChatProvider(
        _Provider(),
        engine,  # type: ignore[arg-type]
        reservation_usd=Decimal("0.10"),
        input_price_per_million_usd=Decimal("1"),
        output_price_per_million_usd=Decimal("2"),
        max_prompt_tokens=max_prompt_tokens,
    )
    provider.bind_run(uuid4())
    return provider


def test_source_scope_rejects_duplicate_document_ids() -> None:
    document_id = uuid4()
    with pytest.raises(ValidationError):
        SourceScope(document_ids=[document_id, document_id])


def test_workflow_budget_reserves_before_call_and_persists_usage() -> None:
    engine = _Engine()
    result = _budgeted(engine).complete([{"role": "user", "content": "evidence"}])

    assert result.prompt_tokens == 100
    statements = "\n".join(engine.connection.statements)
    assert "budget_reserved_usd=budget_reserved_usd+" in statements
    assert "actual_cost_usd=actual_cost_usd+" in statements
    assert "input_tokens,output_tokens,cost_usd" in statements


def test_workflow_budget_fails_before_provider_when_reservation_is_denied() -> None:
    with pytest.raises(WorkflowBudgetExceeded):
        _budgeted(_Engine(claimed=False)).complete([{"role": "user", "content": "evidence"}])


def test_workflow_budget_rejects_oversized_prompt_before_database_reservation() -> None:
    engine = _Engine()
    with pytest.raises(WorkflowBudgetExceeded):
        _budgeted(engine, max_prompt_tokens=1).complete(
            [{"role": "user", "content": "a prompt that exceeds the bounded context"}]
        )
    assert engine.connection.statements == []


def test_pipeline_runtime_configuration_is_not_an_unvalidated_label() -> None:
    configured = PipelineRuntimeConfig.model_validate(
        {
            "retrieval_limit": 7,
            "model": "z-ai/glm-5.2",
            "evaluation_prompt_version": "grounded-answer-v1",
            "retrieval_mode": "dense_sparse_rerank",
        }
    )
    assert configured.retrieval_limit == 7
    with pytest.raises(ValidationError):
        PipelineRuntimeConfig.model_validate(
            {"retrieval_limit": 0, "model": "x", "evaluation_prompt_version": "arbitrary"}
        )
