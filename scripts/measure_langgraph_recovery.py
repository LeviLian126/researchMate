"""Measure durable LangGraph interrupt recovery across process restarts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from researchmate_worker.evidence_graph import EvidenceWorkflowState

DATABASE_URL_ENV = "RECOVERY_BENCHMARK_DATABASE_URL"
DEFAULT_TRIALS = 1_000
DEFAULT_BATCH_SIZE = 50
DEFAULT_MINIMUM_RATE = 0.995
DEFAULT_CONFIDENCE = 0.95


@dataclass(frozen=True)
class PhaseResult:
    """Summarize one child-process benchmark phase."""

    attempted: int
    successful: int
    failures: list[str]


class BenchmarkDomain:
    """Provide deterministic, network-free behavior for the production graph."""

    def plan(self, _state: EvidenceWorkflowState) -> dict[str, list[str]]:
        return {"questions": ["first", "second"]}

    def retrieve_and_extract(
        self, state: EvidenceWorkflowState
    ) -> dict[str, list[dict[str, object]]]:
        question = str(state["question"])
        return {"evidence_batches": [{"question": question, "claims": []}]}

    def reconcile(self, _state: EvidenceWorkflowState) -> dict[str, list[object]]:
        return {"claims": [], "relations": []}

    def review_payload(self, _state: EvidenceWorkflowState) -> dict[str, object]:
        return {"claims": [], "reason": "durable recovery benchmark"}

    def apply_decision(
        self, _state: EvidenceWorkflowState, decision: dict[str, object]
    ) -> dict[str, object]:
        return {"decision": decision}

    def synthesize(self, _state: EvidenceWorkflowState) -> dict[str, dict[str, str]]:
        return {"report": {"title": "resumed report"}}

    def validate_and_commit(self, _state: EvidenceWorkflowState) -> dict[str, dict[str, bool]]:
        return {"validation": {"passed": True}}


def zero_failure_lower_bound(successful: int, confidence: float) -> float:
    """Return the exact one-sided binomial lower bound when no failures occurred."""
    if successful <= 0:
        return 0.0
    alpha = 1.0 - confidence
    return alpha ** (1.0 / successful)


def _initial_state(thread_id: str) -> EvidenceWorkflowState:
    from researchmate_worker.evidence_graph import EvidenceWorkflowState

    return EvidenceWorkflowState(
        run_id=thread_id,
        user_id="benchmark-user",
        project_id="benchmark-project",
        research_goal="verify durable recovery",
        review_policy="strict",
        evidence_batches=[],
    )


def _run_phase(phase: str, thread_ids: list[str], database_url: str) -> PhaseResult:
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from langgraph.types import Command
    from researchmate_worker.evidence_graph import build_evidence_graph

    failures: list[str] = []
    with PostgresSaver.from_conn_string(database_url) as saver:
        strict_saver = PostgresSaver(saver.conn, serde=JsonPlusSerializer(pickle_fallback=False))
        graph = build_evidence_graph(BenchmarkDomain(), strict_saver)
        for thread_id in thread_ids:
            config = {"configurable": {"thread_id": thread_id}}
            try:
                if phase == "interrupt":
                    result = graph.invoke(_initial_state(thread_id), config=config)
                    valid = bool(result.get("__interrupt__"))
                else:
                    result = graph.invoke(Command(resume={"decision": "approve"}), config=config)
                    batches = result.get("evidence_batches", [])
                    questions = sorted(str(batch["question"]) for batch in batches)
                    valid = (
                        result.get("validation") == {"passed": True}
                        and result.get("decision") == {"decision": "approve"}
                        and questions == ["first", "second"]
                    )
                if not valid:
                    failures.append(f"{thread_id}:unexpected_state")
            except (RuntimeError, ValueError, TypeError, KeyError) as exc:
                failures.append(f"{thread_id}:{type(exc).__name__}")
    return PhaseResult(
        attempted=len(thread_ids), successful=len(thread_ids) - len(failures), failures=failures
    )


def _run_child(phase: str, thread_ids: list[str]) -> int:
    database_url = os.environ.get(DATABASE_URL_ENV, "")
    if not database_url:
        raise RuntimeError(f"{DATABASE_URL_ENV} is required")
    result = _run_phase(phase, thread_ids, database_url)
    print(json.dumps(asdict(result), separators=(",", ":")))
    return 0 if not result.failures else 1


def _invoke_child(phase: str, thread_ids: list[str]) -> PhaseResult:
    command = [
        sys.executable,
        str(__file__),
        "--phase",
        phase,
        "--thread-ids",
        ",".join(thread_ids),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    output_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not output_lines:
        detail = completed.stderr.strip() or f"child exited {completed.returncode}"
        return PhaseResult(len(thread_ids), 0, [detail])
    payload = json.loads(output_lines[-1])
    return PhaseResult(
        attempted=int(payload["attempted"]),
        successful=int(payload["successful"]),
        failures=[str(item) for item in payload["failures"]],
    )


def _setup_checkpoint_schema(database_url: str) -> None:
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(database_url) as saver:
        saver.setup()


def run_benchmark(trials: int, batch_size: int, minimum_rate: float, confidence: float) -> int:
    """Run durable checkpoint trials and print the measured recovery result."""
    database_url = os.environ.get(DATABASE_URL_ENV, "")
    if not database_url:
        raise RuntimeError(f"{DATABASE_URL_ENV} is required")
    _setup_checkpoint_schema(database_url)

    prefix = f"recovery-{uuid4()}"
    failures: list[str] = []
    process_restarts = 0
    for offset in range(0, trials, batch_size):
        size = min(batch_size, trials - offset)
        thread_ids = [f"{prefix}-{index}" for index in range(offset, offset + size)]
        interrupted = _invoke_child("interrupt", thread_ids)
        process_restarts += 1
        if interrupted.failures:
            failures.extend(f"{thread_id}:interrupt_batch_failed" for thread_id in thread_ids)
            continue
        resumed = _invoke_child("resume", thread_ids)
        failures.extend(resumed.failures)

    successful = trials - len(failures)
    success_rate = successful / trials
    lower_bound = zero_failure_lower_bound(successful, confidence) if not failures else 0.0
    passed = success_rate >= minimum_rate and lower_bound >= minimum_rate
    result = {
        "trials": trials,
        "successful": successful,
        "failures": len(failures),
        "success_rate": round(success_rate, 6),
        "confidence": confidence,
        "one_sided_lower_bound": round(lower_bound, 6),
        "minimum_rate": minimum_rate,
        "process_restarts": process_restarts,
        "passed": passed,
        "failure_samples": failures[:10],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 1


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def parse_args() -> argparse.Namespace:
    """Parse benchmark command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=_positive_int, default=DEFAULT_TRIALS)
    parser.add_argument("--batch-size", type=_positive_int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--minimum-rate", type=float, default=DEFAULT_MINIMUM_RATE)
    parser.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE)
    parser.add_argument("--phase", choices=("interrupt", "resume"))
    parser.add_argument("--thread-ids", default="")
    return parser.parse_args()


def main() -> int:
    """Run either the controller or one isolated child-process phase."""
    args = parse_args()
    if args.phase:
        thread_ids = [item for item in args.thread_ids.split(",") if item]
        if not thread_ids:
            raise RuntimeError("--thread-ids is required for child phases")
        return _run_child(args.phase, thread_ids)
    if not 0.0 < args.minimum_rate <= 1.0:
        raise RuntimeError("--minimum-rate must be in (0, 1]")
    if not 0.0 < args.confidence < 1.0:
        raise RuntimeError("--confidence must be in (0, 1)")
    return run_benchmark(args.trials, args.batch_size, args.minimum_rate, args.confidence)


if __name__ == "__main__":
    raise SystemExit(main())
