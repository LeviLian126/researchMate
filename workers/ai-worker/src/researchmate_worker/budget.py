from __future__ import annotations

from decimal import Decimal
import json
from time import monotonic
from typing import Iterable
from uuid import UUID

from sqlalchemy import Engine, text

from researchmate_api.services.llm import ChatProvider, LLMResult


class WorkflowBudgetExceeded(RuntimeError):
    code = "WORKFLOW_BUDGET_EXCEEDED"
    retryable = False


class BudgetedChatProvider:
    """Atomically reserve a per-call ceiling and persist provider usage per workflow."""

    def __init__(
        self,
        delegate: ChatProvider,
        engine: Engine,
        *,
        reservation_usd: Decimal,
        input_price_per_million_usd: Decimal,
        output_price_per_million_usd: Decimal,
        max_prompt_tokens: int,
    ) -> None:
        self.delegate = delegate
        self.engine = engine
        self.reservation_usd = reservation_usd
        self.input_price = input_price_per_million_usd
        self.output_price = output_price_per_million_usd
        self.max_prompt_tokens = max_prompt_tokens
        self.run_id: UUID | None = None
        delegate_settings = getattr(delegate, "settings", None)
        self.model = getattr(delegate_settings, "nvidia_model", None)

    def bind_run(self, run_id: UUID) -> None:
        self.run_id = run_id

    def complete(self, messages: Iterable[dict[str, str]]) -> LLMResult:
        if self.run_id is None:
            raise RuntimeError("workflow budget provider is not bound to a run")
        safe_messages = list(messages)
        estimated_prompt_tokens = sum(
            len(message.get("content", "")) for message in safe_messages
        ) // 4 + 1
        if estimated_prompt_tokens > self.max_prompt_tokens:
            raise WorkflowBudgetExceeded()
        self._reserve()
        started = monotonic()
        result = self.delegate.complete(safe_messages)
        latency_ms = max(0, round((monotonic() - started) * 1000))
        input_tokens = int(result.prompt_tokens or 0)
        output_tokens = int(result.completion_tokens or 0)
        actual = (
            Decimal(input_tokens) * self.input_price
            + Decimal(output_tokens) * self.output_price
        ) / Decimal(1_000_000)
        self._record_usage(result, latency_ms, input_tokens, output_tokens, actual)
        return result

    def _reserve(self) -> None:
        with self.engine.begin() as connection:
            reserved = connection.execute(
                text(
                    """
                    update workflow_runs
                    set budget_reserved_usd=budget_reserved_usd+:amount
                    where id=:run_id and status in ('pending','running')
                      and budget_reserved_usd+:amount<=budget_limit_usd
                    returning budget_reserved_usd
                    """
                ),
                {"run_id": self.run_id, "amount": self.reservation_usd},
            ).one_or_none()
        if reserved is None:
            raise WorkflowBudgetExceeded()

    def _record_usage(
        self,
        result: LLMResult,
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        actual: Decimal,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text("select pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": str(self.run_id)},
            )
            connection.execute(
                text(
                    """
                    update workflow_runs set actual_cost_usd=actual_cost_usd+:actual
                    where id=:run_id
                    """
                ),
                {"run_id": self.run_id, "actual": actual},
            )
            connection.execute(
                text(
                    """
                    insert into run_events(
                      run_id,sequence,node_key,event_type,attempt,status,safe_payload,
                      latency_ms,input_tokens,output_tokens,cost_usd
                    ) values (
                      :run_id,
                      coalesce((select max(sequence)+1 from run_events where run_id=:run_id),0),
                      'llm_provider','node_completed',1,'succeeded',cast(:payload as jsonb),
                      :latency_ms,:input_tokens,:output_tokens,:cost_usd
                    )
                    """
                ),
                {
                    "run_id": self.run_id,
                    "payload": json.dumps({"model": result.model}, separators=(",", ":")),
                    "latency_ms": latency_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": actual,
                },
            )
