#!/usr/bin/env python3
"""Validate Humanizer's portable package surfaces without external dependencies."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
PLUGIN = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
PATTERN_PATHS = [
    ROOT / "references" / "content-and-language-patterns.md",
    ROOT / "references" / "style-and-communication-patterns.md",
    ROOT / "references" / "filler-rhetoric-and-detection.md",
]
TECHNICAL_STYLE_PATH = ROOT / "references" / "technical-documentation-and-bilingual-style.md"


def require(match: re.Match[str] | None, message: str) -> re.Match[str]:
    """Return a required regex match or stop with a precise validation error."""
    if match is None:
        raise SystemExit(message)
    return match


frontmatter = require(
    re.match(r"\A---\n(.*?)\n---\n", SKILL, re.DOTALL),
    "SKILL.md must start with YAML frontmatter",
).group(1)

for nonportable_key in ("compatibility:", "allowed-tools:"):
    if re.search(rf"(?m)^{re.escape(nonportable_key)}", frontmatter):
        raise SystemExit(f"Remove nonportable frontmatter key: {nonportable_key[:-1]}")

skill_version = require(
    re.search(r'(?m)^\s+version:\s*["\']([^"\']+)["\']\s*$', frontmatter),
    "SKILL.md metadata.version is missing",
).group(1)
readme_version = require(
    re.search(r"(?m)^- \*\*([0-9]+\.[0-9]+\.[0-9]+)\*\*", README),
    "README version history is missing",
).group(1)

versions = {skill_version, readme_version, str(PLUGIN.get("version", ""))}
if len(versions) != 1:
    raise SystemExit(f"Version mismatch: {sorted(versions)}")

for path in [*PATTERN_PATHS, TECHNICAL_STYLE_PATH]:
    if not path.is_file():
        raise SystemExit(f"Missing progressive-disclosure reference: {path.relative_to(ROOT)}")
    relative = path.relative_to(ROOT).as_posix()
    if relative not in SKILL:
        raise SystemExit(f"SKILL.md must route to {relative}")

pattern_text = "\n".join(path.read_text(encoding="utf-8") for path in PATTERN_PATHS)
pattern_numbers = [
    int(number)
    for number in re.findall(r"(?m)^### ([0-9]+)\. ", pattern_text)
]
if sorted(pattern_numbers) != list(range(1, 34)) or len(pattern_numbers) != 33:
    raise SystemExit(f"Expected patterns 1-33 exactly once, found {pattern_numbers}")

readme_numbers = {
    int(number) for number in re.findall(r"(?m)^\| ([0-9]+) \|", README)
}
if readme_numbers != set(range(1, 34)):
    raise SystemExit("README pattern table must contain patterns 1-33")

if len(SKILL.splitlines()) > 500:
    raise SystemExit("SKILL.md exceeds the 500-line portability budget")

for path in PATTERN_PATHS:
    if len(path.read_text(encoding="utf-8").splitlines()) > 500:
        raise SystemExit(f"Pattern reference exceeds 500 lines: {path.relative_to(ROOT)}")

print(f"Humanizer package v{skill_version} is valid")
