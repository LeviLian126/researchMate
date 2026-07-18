#!/usr/bin/env python3
"""Validate the single-entry Indie Product Delivery skill package."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

NODE_FILES = {
    "00-product-delivery-kernel": ["README.md"],
    "01-market-mvp-scope": [
        "README.md",
        "product-discovery-scope-and-acceptance.md",
        "market-validation-positioning-and-trust.md",
    ],
    "02-architecture-contracts-plan": [
        "README.md",
        "system-boundaries-data-and-trust-contracts.md",
        "architecture-evolution-and-build-plan.md",
    ],
    "03-backend-api-data-build": [
        "README.md",
        "backend-slice-domain-and-interface-build.md",
        "persistence-provider-and-async-build.md",
        "backend-proof-debug-and-observability.md",
    ],
    "04-frontend-ux-ui-build": [
        "README.md",
        "experience-flow-content-and-states.md",
        "visual-direction-prototype-and-redesign.md",
        "frontend-responsive-accessible-build.md",
        "browser-proof-and-visual-debug.md",
    ],
    "05-qa-review-security-hardening": [
        "README.md",
        "quality-scope-and-diff-review.md",
        "runtime-reliability-and-security-proof.md",
        "quality-decision-and-release-readiness.md",
    ],
    "06-ci-cd-launch": [
        "README.md",
        "release-readiness-environment-and-pipeline.md",
        "rollout-recovery-verification-and-record.md",
    ],
    "07-ops-growth-iteration": [
        "README.md",
        "production-health-and-signal-integrity.md",
        "customer-evidence-experiments-and-next-slice.md",
    ],
}

REQUIRED_PATHS = [
    "SKILL.md",
    "agents/openai.yaml",
    "references/durable-document-quality.md",
    *[
        f"references/nodes/{node}/{filename}"
        for node, filenames in NODE_FILES.items()
        for filename in filenames
    ],
    "references/agent-context-html/instructions.md",
    "references/agent-context-html/references/content-model.md",
    "references/agent-context-html/references/visual-interaction.md",
    "references/agent-context-html/references/validation.md",
    "references/agent-context-html/assets/document-system.css",
    "references/agent-context-html/evals/evals.json",
    "scripts/validate_package.py",
    "scripts/smoke_test.py",
    "scripts/run_routing_eval.py",
    "scripts/run_agent_eval.py",
    "tests/document-quality/evals.json",
    "tests/document-quality/trigger-evals.json",
    "tests/routing/expected.json",
]

FORBIDDEN_LEGACY_PATHS = [
    "assets/templates",
    "references/README.md",
    "references/CHANGELOG.md",
    "references/output-registry.md",
    "references/shared",
    "references/agent-context-html/SKILL.md",
    "scripts/init_docs_assets.py",
    "scripts/lint_instruction_consistency.py",
    "scripts/render_template.py",
    "scripts/validate_docs.py",
    "tests/fixtures",
]

ALLOWED_FRONTMATTER_KEYS = {"name", "description"}
PACKAGE_PREFIXES = ("references/", "assets/", "scripts/", "agents/", "tests/")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CODE_RE = re.compile(r"`([^`\r\n]+)`")


def extract_frontmatter(path: Path) -> tuple[dict, str, list[str]]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not match:
        return {}, text, [f"{path.relative_to(ROOT)} missing YAML frontmatter"]
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return {}, text[match.end() :], [f"invalid frontmatter in {path.relative_to(ROOT)}: {exc}"]
    if not isinstance(data, dict):
        return {}, text[match.end() :], [f"frontmatter must be a mapping in {path.relative_to(ROOT)}"]
    return data, text[match.end() :], []


def check_skill(path: Path, findings: list[str]) -> None:
    data, body, errors = extract_frontmatter(path)
    findings.extend(errors)
    if errors:
        return
    extra = set(data) - ALLOWED_FRONTMATTER_KEYS
    if extra:
        findings.append(f"unexpected frontmatter keys: {sorted(extra)}")
    if data.get("name") != "indie-product-delivery":
        findings.append("root skill name must be indie-product-delivery")
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        findings.append("root skill description is missing")
    if "references/nodes/00-product-delivery-kernel/README.md" not in body:
        findings.append("root SKILL.md must route through Node00")
    if "references/agent-context-html/instructions.md" not in body:
        findings.append("root SKILL.md must expose the internal project-documentation capability")
    if "references/durable-document-quality.md" not in body:
        findings.append("root SKILL.md must expose the durable-document quality protocol")


def candidate_path(token: str, source: Path) -> Path | None:
    token = token.strip().split("#", 1)[0]
    if not token or token.startswith(("http://", "https://", "mailto:", "tel:", "#")):
        return None
    if any(char in token for char in "*{}<>") or token.startswith("docs/"):
        return None
    if token.startswith(PACKAGE_PREFIXES):
        return ROOT / token
    if token.startswith(("./", "../")):
        return source.parent / token
    if "/" not in token and "\\" not in token and Path(token).suffix.lower() == ".md":
        return source.parent / token
    return None


def check_references(findings: list[str]) -> None:
    for source in sorted(ROOT.rglob("*.md")):
        text = source.read_text(encoding="utf-8")
        for token in [*CODE_RE.findall(text), *LINK_RE.findall(text)]:
            candidate = candidate_path(token, source)
            if candidate is not None and not candidate.resolve().exists():
                findings.append(f"broken package reference in {source.relative_to(ROOT)}: {token}")


def check_metadata(findings: list[str]) -> None:
    path = ROOT / "agents/openai.yaml"
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        findings.append(f"invalid agents/openai.yaml: {exc}")
        return
    interface = payload.get("interface") if isinstance(payload, dict) else None
    if not isinstance(interface, dict):
        findings.append("agents/openai.yaml needs an interface mapping")
        return
    expected = {"display_name", "short_description", "default_prompt"}
    if set(interface) != expected:
        findings.append(f"agents/openai.yaml interface keys must be {sorted(expected)}")
    prompt = interface.get("default_prompt")
    if not isinstance(prompt, str) or "$indie-product-delivery" not in prompt:
        findings.append("default_prompt must mention $indie-product-delivery")


def check_agent_context(findings: list[str]) -> None:
    instructions = ROOT / "references/agent-context-html/instructions.md"
    if instructions.read_text(encoding="utf-8").startswith("---\n"):
        findings.append("agent-context instructions must not contain Skill frontmatter")
    path = ROOT / "references/agent-context-html/evals/evals.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"invalid agent-context eval set: {exc}")
        return
    cases = payload.get("evals") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("capability_name") != "agent-context-html"
        or not isinstance(cases, list)
        or len(cases) < 5
    ):
        findings.append("agent-context eval set must name the internal capability and contain at least five cases")
    elif any(
        not isinstance(case, dict) or not case.get("prompt") or not case.get("expected_output")
        for case in cases
    ):
        findings.append("agent-context eval cases need prompt and expected_output")


def check_document_quality_evals(findings: list[str]) -> None:
    path = ROOT / "tests/document-quality/evals.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"invalid durable-document eval set: {exc}")
        return
    cases = payload.get("evals") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("skill_name") != "indie-product-delivery"
        or not isinstance(cases, list)
        or len(cases) < 5
    ):
        findings.append("durable-document eval set must name the skill and contain at least five cases")
    elif any(
        not isinstance(case, dict)
        or not isinstance(case.get("id"), int)
        or not case.get("prompt")
        or not case.get("expected_output")
        or not isinstance(case.get("files"), list)
        or not isinstance(case.get("expectations"), list)
        or len(case["expectations"]) < 3
        for case in cases
    ):
        findings.append("durable-document eval cases need numeric id, prompt, expected_output, files, and three expectations")


def check_document_quality_trigger_evals(findings: list[str]) -> None:
    path = ROOT / "tests/document-quality/trigger-evals.json"
    try:
        cases = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"invalid durable-document trigger eval set: {exc}")
        return
    if not isinstance(cases, list) or len(cases) < 6:
        findings.append("durable-document trigger eval set must contain at least six cases")
    elif any(
        not isinstance(case, dict)
        or not isinstance(case.get("query"), str)
        or not case["query"].strip()
        or not isinstance(case.get("should_trigger"), bool)
        for case in cases
    ):
        findings.append("durable-document trigger cases need query and boolean should_trigger")
    elif not any(case["should_trigger"] for case in cases) or not any(
        not case["should_trigger"] for case in cases
    ):
        findings.append("durable-document trigger evals need positive and negative cases")


def check_routing_prompts(findings: list[str]) -> None:
    expected_path = ROOT / "tests/routing/expected.json"
    prompt_dir = ROOT / "tests/routing/prompts"
    try:
        payload = json.loads(expected_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"invalid routing eval set: {exc}")
        return
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        findings.append("routing eval set must contain cases")
        return
    referenced = {
        (ROOT / case["prompt_file"]).resolve()
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("prompt_file"), str)
    }
    actual = {path.resolve() for path in prompt_dir.glob("*.txt")}
    missing = sorted(path.relative_to(ROOT).as_posix() for path in referenced - actual)
    unused = sorted(path.relative_to(ROOT).as_posix() for path in actual - referenced)
    if missing:
        findings.append(f"missing routing prompts: {missing}")
    if unused:
        findings.append(f"unreferenced routing prompts: {unused}")


def main() -> int:
    findings: list[str] = []
    for rel in REQUIRED_PATHS:
        if not (ROOT / rel).exists():
            findings.append(f"missing required path: {rel}")
    for rel in FORBIDDEN_LEGACY_PATHS:
        if (ROOT / rel).exists():
            findings.append(f"forbidden legacy path present: {rel}")

    reference_dirs = sorted(path.name for path in (ROOT / "references").iterdir() if path.is_dir())
    if reference_dirs != ["agent-context-html", "nodes"]:
        findings.append(f"unexpected reference directories: {reference_dirs}")

    generated = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"} or path.name == ".DS_Store"
    )
    if generated:
        findings.append(f"generated/cache files must not be packaged: {generated}")

    skill_files = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.rglob("SKILL.md"))
    if skill_files != ["SKILL.md"]:
        findings.append(f"the package must contain exactly one root SKILL.md: {skill_files}")

    if (ROOT / "SKILL.md").exists():
        check_skill(ROOT / "SKILL.md", findings)
    check_metadata(findings)
    check_references(findings)
    check_agent_context(findings)
    check_document_quality_evals(findings)
    check_document_quality_trigger_evals(findings)
    check_routing_prompts(findings)

    if findings:
        print("blocker findings:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Indie Product Delivery package structure and references OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
