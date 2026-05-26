#!/usr/bin/env python3
"""Validate a generated agent context dashboard.

Usage:
  python validate_context_dashboard.py /path/to/repo/context
"""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REQUIRED_SECTION_IDS = [
    "resume", "start-here", "next-actions", "blockers", "files",
    "repo-map", "handoff", "validation", "risks", "decision-gates", "context-health", "completion-status", "sources",
]
REMOTE_RE = re.compile(r"^(https?:)?//", re.I)
REMOTE_TAGS = {"script", "link", "img", "iframe", "source", "video", "audio"}

class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.h1 = 0
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.remote_assets: list[str] = []
        self.text_parts: list[str] = []
        self.in_script_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: v or "" for k, v in attrs}
        if tag in {"script", "style"}:
            self.in_script_style = True
        if tag == "h1":
            self.h1 += 1
        if "id" in d:
            self.ids.add(d["id"])
        if tag == "a" and "href" in d:
            self.links.append(d["href"])
        for attr in ["src", "href"]:
            if attr in d and tag in REMOTE_TAGS and REMOTE_RE.match(d[attr]):
                self.remote_assets.append(f"{tag} {attr}={d[attr]}")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.in_script_style = False

    def handle_data(self, data: str) -> None:
        if not self.in_script_style and data.strip():
            self.text_parts.append(data.strip())

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)


def validate_context(root: Path) -> tuple[list[str], list[str]]:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    required = [
        root / "index.html",
        root / "assets" / "site.css",
        root / "assets" / "site.js",
        root / "context-state.json",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    html_path = root / "index.html"
    parser = Parser()
    if html_path.exists():
        parser.feed(html_path.read_text(encoding="utf-8", errors="replace"))
        if parser.h1 != 1:
            errors.append(f"index.html must contain exactly one h1, found {parser.h1}")
        for sid in REQUIRED_SECTION_IDS:
            if sid not in parser.ids:
                errors.append(f"missing required section id: {sid}")
        for item in parser.remote_assets:
            errors.append(f"remote asset found: {item}")
        if "Source audit" not in parser.text:
            errors.append("visible Source audit section missing")
        if "Next actions" not in parser.text:
            errors.append("visible Next actions section missing")
        if "Decision gates" not in parser.text:
            errors.append("visible Decision gates section missing")
        if "Context health" not in parser.text:
            errors.append("visible Context health section missing")
        if "Completion status" not in parser.text:
            errors.append("visible Completion status section missing")
        for href in parser.links:
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                if href.startswith("#") and href[1:] and href[1:] not in parser.ids:
                    errors.append(f"broken same-page anchor: {href}")
                continue
            if REMOTE_RE.match(href):
                continue
            target = (html_path.parent / href.split("#", 1)[0]).resolve()
            if not target.exists():
                errors.append(f"broken relative link: {href}")

    css_path = root / "assets" / "site.css"
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8", errors="replace")
        for token in ["--bg", "--surface", "--text", "--muted", "--line", "--brand", "--brand-contrast"]:
            if token not in css:
                errors.append(f"missing css token: {token}")
        if "html[data-mode=\"dark\"]" not in css and "html[data-mode='dark']" not in css:
            errors.append("missing dark-mode css hook")

    js_path = root / "assets" / "site.js"
    if js_path.exists():
        js = js_path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\b(fetch|XMLHttpRequest|sendBeacon)\s*\(", js):
            errors.append("network call found in site.js")

    state_path = root / "context-state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"context-state.json is invalid: {exc}")
            state = {}
        required_keys = [
            "schema_version", "generated_at", "repo", "branch", "status", "confidence",
            "objective", "next_actions", "blockers", "changed_files", "important_files",
            "tests_run", "tests_not_run", "risks", "decision_gates", "completion_status", "context_health", "sources_used", "sources_missing",
        ]
        for key in required_keys:
            if key not in state:
                errors.append(f"context-state.json missing key: {key}")
        if isinstance(state.get("next_actions"), list) and not state["next_actions"]:
            warnings.append("next_actions is empty")
        if isinstance(state.get("sources_used"), list) and not state["sources_used"]:
            warnings.append("sources_used is empty; dashboard is likely inferred only")
        if state.get("confidence") == "low":
            warnings.append("dashboard confidence is low; explicit handoff/state files may be missing")

    return errors, warnings


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip())
        return 2
    errors, warnings = validate_context(Path(argv[0]))
    print("Agent context dashboard validation")
    if warnings:
        print("\nwarnings:")
        for warning in warnings:
            print(f"  - {warning}")
    if errors:
        print("\nerrors:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("\npassed: dashboard satisfies static context contract")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
