import json
from contextlib import nullcontext
from uuid import UUID

from researchmate_worker.fault_simulation import FaultSimulationService


class FakeResult:
    def __init__(self, row=None):
        self.row = row

    def mappings(self):
        return self

    def one_or_none(self):
        return self.row


class FakeConnection:
    def __init__(self):
        self.finished = None

    def execute(self, statement, params):
        sql = str(statement)
        if "returning id,scenario,target_run_id,attempts" in sql:
            return FakeResult(
                {
                    "id": UUID(int=1),
                    "scenario": "worker_interrupt",
                    "target_run_id": UUID(int=2),
                    "attempts": 1,
                }
            )
        if "select id,status,error_code from workflow_runs" in sql:
            return FakeResult({"id": UUID(int=2), "status": "running", "error_code": None})
        if "update fault_exercises set status=:status" in sql:
            self.finished = params
            return FakeResult()
        raise AssertionError(sql)


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()

    def begin(self):
        return nullcontext(self.connection)


def test_fault_simulation_records_recovery_without_external_mutation() -> None:
    engine = FakeEngine()
    service = FaultSimulationService(engine)  # type: ignore[arg-type]

    assert service.run(UUID(int=1), worker_id="test-worker") == "succeeded"

    finished = engine.connection.finished
    assert finished["status"] == "succeeded"
    result = json.loads(finished["result"])
    assert result["simulation_only"] is True
    assert result["external_calls"] == 0
    assert result["recovery_state"] == "runtime_unchanged"
    assert result["target_snapshot"]["status"] == "running"
