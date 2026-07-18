#!/usr/bin/env python3
"""Run explicit, read-only Codex behavior evaluation for this skill.

This command is intentionally separate from smoke_test.py because it consumes model
time. It runs one ephemeral Codex session over independent routing cases, constrains
the final response with JSON Schema, and scores it against expected metadata.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from run_routing_eval import (
    EXPECTED,
    ROOT,
    VALID_ACTIVATIONS,
    VALID_GATES,
    VALID_MUTATIONS,
    VALID_OWNERS,
    VALID_PRECONDITIONS,
    VALID_RISKS,
    VALID_SCOPES,
    VALID_STATUSES,
    VALID_TARGETS,
    compare_actual,
    load_json,
    validate_expected,
)


def enum(values: set[str]) -> dict:
    return {"type": "string", "enum": sorted(values)}


def output_schema(case_count: int) -> dict:
    item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "activation",
            "initial_owner",
            "scope",
            "risk",
            "external_effect",
            "mutation",
            "required_preconditions",
            "required_gates",
            "terminal_target",
            "terminal_status",
        ],
        "properties": {
            "id": {"type": "string"},
            "activation": enum(VALID_ACTIVATIONS),
            "initial_owner": enum(VALID_OWNERS),
            "scope": enum(VALID_SCOPES),
            "risk": enum(VALID_RISKS),
            "external_effect": {"type": "boolean"},
            "mutation": enum(VALID_MUTATIONS),
            "required_preconditions": {
                "type": "array",
                "uniqueItems": True,
                "items": enum(VALID_PRECONDITIONS),
            },
            "required_gates": {
                "type": "array",
                "uniqueItems": True,
                "items": enum(VALID_GATES),
            },
            "terminal_target": enum(VALID_TARGETS),
            "terminal_status": enum(VALID_STATUSES),
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["cases"],
        "properties": {
            "cases": {
                "type": "array",
                "minItems": case_count,
                "maxItems": case_count,
                "items": item,
            }
        },
    }


def build_prompt(cases: list[dict]) -> str:
    requests = [
        {
            "id": case["id"],
            "request": (ROOT / case["prompt_file"]).read_text(encoding="utf-8").strip(),
        }
        for case in cases
    ]
    return f"""Evaluate how the local $indie-product-delivery skill should handle each independent request.

Read {ROOT / 'SKILL.md'} and the Node00 kernel. Read only additional local references needed to apply the skill accurately. Do not execute the user requests, modify files, invoke subagents, or perform external actions. Return only the JSON required by the supplied schema.

Classify each request independently:
- activation is AUTO when the skill metadata should trigger implicitly; use EXPLICIT_ONLY for an isolated, fully specified local task or work wholly owned by a specialized skill that this skill should handle only when named.
- initial_owner is the owner of the first present decision/action, not every later lifecycle node.
- scope, risk, and external_effect are independent. Classify the requested action, not sensitive nouns.
- required_preconditions lists every named prerequisite that must be confirmed before the requested action, including prerequisites the prompt says are already satisfied.
- required_gates lists only real cross-node product, contract, quality, security, or release gates.
- terminal_target follows the original request; do not assume deployment.
- terminal_status predicts how the task can honestly finish from the facts and tool limitations expressly stated. Assume ordinary authorized local work succeeds unless the prompt states a blocker.

Use these exact precondition labels: {', '.join(sorted(VALID_PRECONDITIONS))}.
Use these exact gate labels: {', '.join(sorted(VALID_GATES))}.

Requests:
{json.dumps(requests, ensure_ascii=False, indent=2)}
"""


def find_codex() -> str:
    candidates = ["codex.cmd", "codex"] if sys.platform == "win32" else ["codex"]
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    raise SystemExit("codex CLI was not found on PATH")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("core", "full"), default="core")
    parser.add_argument("--model", help="optional Codex model override")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--actual-out", type=Path, help="optional path to retain the structured result")
    args = parser.parse_args()

    cases = validate_expected(load_json(EXPECTED), suite=args.suite)
    with tempfile.TemporaryDirectory(prefix="indie-product-delivery-eval-") as temp_dir:
        temp = Path(temp_dir)
        schema_path = temp / "schema.json"
        actual_path = temp / "actual.json"
        schema_path.write_text(
            json.dumps(output_schema(len(cases)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        cmd = [
            find_codex(),
            "--ask-for-approval",
            "never",
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(actual_path),
            "-C",
            str(ROOT),
        ]
        if args.model:
            cmd.extend(["--model", args.model])
        cmd.append(build_prompt(cases))

        print(f"Running {args.suite} behavior eval with {len(cases)} cases...")
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=args.timeout,
        )
        if proc.stdout:
            print(proc.stdout.rstrip())
        if proc.returncode:
            print(f"codex exec failed with return code {proc.returncode}")
            return proc.returncode
        if not actual_path.is_file():
            print("codex exec did not produce the structured result")
            return 1

        if args.actual_out:
            args.actual_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(actual_path, args.actual_out)
            print(f"Retained actual result at {args.actual_out}")

        return compare_actual(cases, actual_path)


if __name__ == "__main__":
    raise SystemExit(main())
