#!/usr/bin/env python3
"""Validate and score orthogonal Indie Product Delivery routing fixtures.

This deterministic command never calls a model. Pass --actual to score structured
results produced by a human or by run_agent_eval.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "tests/routing/expected.json"

VALID_ACTIVATIONS = {"AUTO", "EXPLICIT_ONLY"}
VALID_OWNERS = {"01", "02", "03", "04", "05", "06", "07", "agent-context"}
VALID_SCOPES = {"LOCAL", "MODULE", "CROSS_BOUNDARY", "PRODUCT_DIRECTION"}
VALID_RISKS = {"STANDARD", "SENSITIVE", "ACTIVE_HARM"}
VALID_MUTATIONS = {
    "PLAN_ONLY",
    "REVIEW_ONLY",
    "CHANGE_AND_VERIFY",
    "EXECUTE_AUTHORIZED",
    "REPORT_ONLY",
}
VALID_PRECONDITIONS = {
    "PRODUCT_SCOPE",
    "SYSTEM_CONTRACT",
    "QUALITY_EVIDENCE",
    "EXACT_AUTHORIZATION",
    "TARGET_AND_ARTIFACT",
    "TARGET_ACCESS",
    "BROWSER_EVIDENCE",
    "TEST_ENVIRONMENT",
    "NEW_EVIDENCE",
    "RECOVERY_PATH",
}
VALID_GATES = {"PRODUCT", "CONTRACT", "QUALITY", "SECURITY", "RELEASE"}
VALID_TARGETS = {
    "PRODUCT_DECISION",
    "SYSTEM_PLAN",
    "VERIFIED_CHANGE",
    "REVIEW_RESULT",
    "SHIP_DECISION",
    "RELEASE_READY",
    "VERIFIED_RELEASE",
    "INCIDENT_CONTAINED",
    "OPERATING_DECISION",
    "CURRENT_DOCUMENTATION",
}
VALID_STATUSES = {
    "DONE",
    "DONE_WITH_CONCERNS",
    "BLOCKED_USER_DECISION",
    "BLOCKED_AUTHORIZATION",
    "BLOCKED_EVIDENCE",
    "ABORTED_UNSAFE",
}
REQUIRED_FIELDS = {
    "id",
    "suite",
    "prompt_file",
    "activation",
    "initial_owner",
    "scope",
    "risk",
    "external_effect",
    "mutation",
    "required_preconditions",
    "required_gates",
    "terminal_target",
    "acceptable_terminal_statuses",
    "forbidden_initial_owners",
    "reason",
}


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid json in {path}: {exc}") from exc


def _enum(case_id: str, field: str, value: object, allowed: set[str]) -> None:
    if value not in allowed:
        raise SystemExit(f"{case_id}: invalid {field}: {value}")


def _enum_list(case_id: str, field: str, value: object, allowed: set[str], *, nonempty: bool = False) -> None:
    if not isinstance(value, list) or (nonempty and not value):
        raise SystemExit(f"{case_id}: {field} must be {'non-empty ' if nonempty else ''}list")
    invalid = set(value) - allowed
    if invalid:
        raise SystemExit(f"{case_id}: invalid {field}: {sorted(invalid)}")
    if len(value) != len(set(value)):
        raise SystemExit(f"{case_id}: duplicate values in {field}")


def validate_expected(data: dict, suite: str = "full") -> list[dict]:
    if data.get("version") != 2:
        raise SystemExit("expected.json must use version 2")
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise SystemExit("expected.json must contain a non-empty cases list")

    seen: set[str] = set()
    cases: list[dict] = []
    for case in raw_cases:
        if not isinstance(case, dict):
            raise SystemExit("each routing case must be an object")
        missing = REQUIRED_FIELDS - set(case)
        if missing:
            raise SystemExit(f"routing case missing fields: {sorted(missing)}")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise SystemExit(f"invalid or duplicate routing case id: {case_id}")
        seen.add(case_id)
        if case["suite"] not in {"core", "full"}:
            raise SystemExit(f"{case_id}: suite must be core or full")

        prompt_path = ROOT / case["prompt_file"]
        if not prompt_path.is_file() or not prompt_path.read_text(encoding="utf-8").strip():
            raise SystemExit(f"{case_id}: missing or empty prompt: {case['prompt_file']}")

        _enum(case_id, "activation", case["activation"], VALID_ACTIVATIONS)
        _enum(case_id, "initial_owner", case["initial_owner"], VALID_OWNERS)
        _enum(case_id, "scope", case["scope"], VALID_SCOPES)
        _enum(case_id, "risk", case["risk"], VALID_RISKS)
        if not isinstance(case["external_effect"], bool):
            raise SystemExit(f"{case_id}: external_effect must be boolean")
        _enum(case_id, "mutation", case["mutation"], VALID_MUTATIONS)
        _enum_list(case_id, "required_preconditions", case["required_preconditions"], VALID_PRECONDITIONS)
        _enum_list(case_id, "required_gates", case["required_gates"], VALID_GATES)
        _enum(case_id, "terminal_target", case["terminal_target"], VALID_TARGETS)
        _enum_list(
            case_id,
            "acceptable_terminal_statuses",
            case["acceptable_terminal_statuses"],
            VALID_STATUSES,
            nonempty=True,
        )
        _enum_list(case_id, "forbidden_initial_owners", case["forbidden_initial_owners"], VALID_OWNERS)
        if case["initial_owner"] in case["forbidden_initial_owners"]:
            raise SystemExit(f"{case_id}: initial owner is also forbidden")
        if not isinstance(case["reason"], str) or not case["reason"].strip():
            raise SystemExit(f"{case_id}: reason must be non-empty")
        if suite == "full" or case["suite"] == "core":
            cases.append(case)
    return cases


def compare_actual(cases: list[dict], actual_path: Path) -> int:
    actual_data = load_json(actual_path)
    actual_cases = {
        case.get("id"): case
        for case in actual_data.get("cases", [])
        if isinstance(case, dict) and isinstance(case.get("id"), str)
    }
    failures: list[str] = []

    scalar_fields = (
        "activation",
        "initial_owner",
        "scope",
        "risk",
        "external_effect",
        "mutation",
        "terminal_target",
    )
    set_fields = ("required_preconditions", "required_gates")

    for expected in cases:
        case_id = expected["id"]
        actual = actual_cases.get(case_id)
        if actual is None:
            failures.append(f"{case_id}: missing actual result")
            continue
        for field in scalar_fields:
            if actual.get(field) != expected[field]:
                failures.append(f"{case_id}: {field} {actual.get(field)!r} != {expected[field]!r}")
        for field in set_fields:
            if set(actual.get(field, [])) != set(expected[field]):
                failures.append(
                    f"{case_id}: {field} {sorted(set(actual.get(field, [])))} != {sorted(expected[field])}"
                )
        status = actual.get("terminal_status")
        if status not in expected["acceptable_terminal_statuses"]:
            failures.append(
                f"{case_id}: terminal_status {status!r} not in {expected['acceptable_terminal_statuses']}"
            )
        if actual.get("initial_owner") in expected["forbidden_initial_owners"]:
            failures.append(f"{case_id}: selected forbidden initial owner {actual.get('initial_owner')}")

    unexpected = set(actual_cases) - {case["id"] for case in cases}
    if unexpected:
        failures.append(f"unexpected actual case ids: {sorted(unexpected)}")

    if failures:
        print("Routing eval failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Routing eval matched {len(cases)} {('core' if len(cases) < len(load_json(EXPECTED)['cases']) else 'full')} cases.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("core", "full"), default="full")
    parser.add_argument("--actual", type=Path, help="structured routing output to compare")
    args = parser.parse_args()

    cases = validate_expected(load_json(EXPECTED), suite=args.suite)
    print("Routing fixture validation passed.")
    print("| id | activation | owner | scope | risk | effect | mutation | target |")
    print("|---|---|---|---|---|---|---|---|")
    for case in cases:
        print(
            f"| {case['id']} | {case['activation']} | {case['initial_owner']} | "
            f"{case['scope']} | {case['risk']} | {case['external_effect']} | "
            f"{case['mutation']} | {case['terminal_target']} |"
        )
    return compare_actual(cases, args.actual) if args.actual else 0


if __name__ == "__main__":
    raise SystemExit(main())
