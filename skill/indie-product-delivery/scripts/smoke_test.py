#!/usr/bin/env python3
"""Run deterministic, model-free smoke checks for the skill package."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    print(f"[{label}] returncode={proc.returncode}")
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.stderr:
        print(proc.stderr.strip())
    if proc.returncode:
        raise SystemExit(f"{label} failed")


def check_project_documentation_evals() -> None:
    path = ROOT / "references/agent-context-html/evals/evals.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("evals", [])
    if payload.get("capability_name") != "agent-context-html" or len(cases) < 5:
        raise SystemExit(
            "project-documentation eval set must name the internal capability and contain at least five cases"
        )
    for case in cases:
        if not isinstance(case, dict) or not case.get("prompt") or not case.get("expected_output"):
            raise SystemExit("every project-documentation eval needs a prompt and expected output")
    print(f"[project_documentation_evals] {len(cases)} valid cases")


def check_document_quality_evals() -> None:
    path = ROOT / "tests/document-quality/evals.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("evals", [])
    if payload.get("skill_name") != "indie-product-delivery" or len(cases) < 5:
        raise SystemExit(
            "durable-document eval set must name the skill and contain at least five cases"
        )
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("id"), int)
            or not case.get("prompt")
            or not case.get("expected_output")
            or not isinstance(case.get("files"), list)
            or not isinstance(case.get("expectations"), list)
            or len(case["expectations"]) < 3
        ):
            raise SystemExit("every durable-document eval needs id, prompt, expected output, files, and expectations")
    print(f"[durable_document_evals] {len(cases)} valid cases")


def check_document_quality_trigger_evals() -> None:
    path = ROOT / "tests/document-quality/trigger-evals.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or len(cases) < 6:
        raise SystemExit("durable-document trigger eval set must contain at least six cases")
    if any(
        not isinstance(case, dict)
        or not isinstance(case.get("query"), str)
        or not case["query"].strip()
        or not isinstance(case.get("should_trigger"), bool)
        for case in cases
    ):
        raise SystemExit("every durable-document trigger eval needs query and boolean should_trigger")
    if not any(case["should_trigger"] for case in cases) or not any(
        not case["should_trigger"] for case in cases
    ):
        raise SystemExit("durable-document trigger evals need positive and negative cases")
    print(f"[durable_document_trigger_evals] {len(cases)} valid cases")


def main() -> int:
    run("validate_package", [sys.executable, "-B", "scripts/validate_package.py"])
    run("routing_eval_fixtures", [sys.executable, "-B", "scripts/run_routing_eval.py", "--suite", "full"])
    check_project_documentation_evals()
    check_document_quality_evals()
    check_document_quality_trigger_evals()
    print("[agent_behavior_eval] skipped by design; run scripts/run_agent_eval.py explicitly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
