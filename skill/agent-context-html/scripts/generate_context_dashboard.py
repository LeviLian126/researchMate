#!/usr/bin/env python3
"""Generate a static HTML context dashboard for coding-agent handoff.

Usage:
  python generate_context_dashboard.py --repo /path/to/repo --out /path/to/repo/context

The script is conservative and dependency-free. It scans known context files,
git metadata, recent commits, selected project manifests, optional gstack
artifacts, and a bounded repo tree. It does not call the network or parse the
full source tree.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", ".next", ".nuxt", ".venv", "venv",
    "coverage", "target", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".turbo", ".cache", ".idea", ".vscode", "out", "tmp", "logs",
}

SOURCE_CANDIDATES = [
    "TASK_STATE.md",
    ".agent/context.json",
    ".agent/handoff.md",
    ".agent/decisions.md",
    "HANDOFF.md",
    "CONTEXT.md",
    "TODO.md",
    "TODOS.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".cursorrules",
    ".windsurfrules",
    "memory-bank/activeContext.md",
    "memory-bank/progress.md",
    "memory-bank/projectbrief.md",
    "memory-bank/systemPatterns.md",
    "memory-bank/techContext.md",
    "README.md",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "Makefile",
]

GSTACK_PATTERNS = [
    "*-design-*.md",
    "*-handoff-*.md",
    "*-ceo-handoff-*.md",
    "ceo-plans/*.md",
    "checkpoints/*.md",
    "timeline.jsonl",
    "*-reviews.jsonl",
]

@dataclass
class SourceRecord:
    path: str
    kind: str
    exists: bool
    summary: str = ""
    mtime: str = ""


def run_git(repo: Path, args: list[str]) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.STDOUT, text=True, timeout=8)
        return True, out.strip()
    except Exception as exc:
        return False, str(exc).strip()


def read_text(path: Path, max_chars: int = 50000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[:max_chars]


def rel(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except Exception:
        return path.as_posix()


def iso_mtime(path: Path) -> str:
    try:
        return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()
    except Exception:
        return ""


def summarize_markdown(text: str, max_items: int = 6) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        if raw.startswith(("#", "- ", "* ", "1. ", "2. ", "3. ")):
            clean = re.sub(r"^#+\s*", "", raw)
            clean = re.sub(r"^[-*]\s*", "", clean)
            clean = re.sub(r"^\d+\.\s*", "", clean)
            if 8 <= len(clean) <= 220:
                items.append(clean)
        if len(items) >= max_items:
            break
    return items


def summarize_text_source(path: Path, max_items: int = 3) -> str:
    text = read_text(path, 20000)
    if path.suffix == ".json" or path.name.endswith(".jsonl"):
        try:
            if path.name.endswith(".jsonl"):
                lines = [ln for ln in text.splitlines() if ln.strip()]
                return f"已抽样 jsonl 记录数：{min(len(lines), 5)}"
            obj = json.loads(text)
            if isinstance(obj, dict):
                return "json 键：" + (", ".join(sorted(obj.keys())[:8]) or "已读取 json")
        except Exception:
            return "已读取类 json 来源，但解析存在警告"
    if path.name in {"package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Makefile"}:
        return "项目命令或配置来源"
    heads = summarize_markdown(text, max_items)
    return "; ".join(heads) if heads else "已读取文本来源"


def extract_json_context(text: str) -> dict:
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def classify_source(path: str) -> str:
    if path.startswith("gstack:"):
        return "gstack-artifact"
    if path.startswith(".agent/") or path == "TASK_STATE.md" or path in {"HANDOFF.md", "CONTEXT.md"}:
        return "agent-state"
    if path in {"AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".windsurfrules"} or "copilot" in path:
        return "agent-instructions"
    if path.startswith("memory-bank/"):
        return "memory-bank"
    if path in {"README.md", "TODO.md", "TODOS.md"}:
        return "project-doc"
    return "project-config"


def slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")


def slug_candidates(repo: Path, remote: str) -> list[str]:
    out: list[str] = [slugify(repo.name)]
    if remote:
        cleaned = remote[:-4] if remote.endswith(".git") else remote
        # Handles https://host/owner/repo and git@host:owner/repo forms.
        m = re.search(r"[:/]([^/:]+)/([^/]+)$", cleaned)
        if m:
            owner, name = slugify(m.group(1)), slugify(m.group(2))
            out.extend([name, f"{owner}-{name}", f"{owner}_{name}"])
    seen: set[str] = set()
    unique: list[str] = []
    for item in out:
        if item and item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def collect_gstack_sources(repo: Path, remote: str) -> list[SourceRecord]:
    base = Path.home() / ".gstack" / "projects"
    if not base.exists():
        return []
    records: list[SourceRecord] = []
    for slug in slug_candidates(repo, remote):
        project = base / slug
        if not project.exists() or not project.is_dir():
            continue
        found: list[Path] = []
        for pattern in GSTACK_PATTERNS:
            try:
                found.extend(project.glob(pattern))
            except Exception:
                pass
        found = sorted({p for p in found if p.is_file()}, key=lambda p: p.stat().st_mtime, reverse=True)[:12]
        for path in found:
            label = f"gstack:{slug}/{path.relative_to(project).as_posix()}"
            records.append(SourceRecord(label, "gstack-artifact", True, summarize_text_source(path, 3), iso_mtime(path)))
    return records


def collect_sources(repo: Path, remote: str) -> tuple[list[SourceRecord], dict]:
    records: list[SourceRecord] = []
    parsed_context: dict = {}

    for candidate in SOURCE_CANDIDATES:
        path = repo / candidate
        if path.exists() and path.is_file():
            text = read_text(path)
            if candidate.endswith(".json"):
                obj = extract_json_context(text)
                parsed_context.update(obj)
                summary = "json 键：" + (", ".join(sorted(obj.keys())[:8]) or "已读取 json")
            else:
                summary = summarize_text_source(path, 3)
            records.append(SourceRecord(candidate, classify_source(candidate), True, summary, iso_mtime(path)))
        else:
            records.append(SourceRecord(candidate, classify_source(candidate), False))

    runs_dir = repo / ".agent" / "runs"
    runs = sorted(runs_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5] if runs_dir.exists() else []
    for path in runs:
        records.append(SourceRecord(rel(repo, path), "run-note", True, summarize_text_source(path, 3), iso_mtime(path)))

    for pattern in ["*handoff*.md", "*HANDOFF*.md", "*context*.md", "*CONTEXT*.md"]:
        for path in sorted(repo.glob(pattern))[:8]:
            r = rel(repo, path)
            if any(s.path == r for s in records):
                continue
            records.append(SourceRecord(r, "handoff-like", True, summarize_text_source(path, 3), iso_mtime(path)))

    records.extend(collect_gstack_sources(repo, remote))
    return records, parsed_context


def repo_tree(repo: Path, max_depth: int = 3, max_entries: int = 180) -> list[str]:
    entries: list[str] = []

    def visible_children(path: Path) -> list[Path]:
        try:
            children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except Exception:
            return []
        return [p for p in children if ((p.name not in SKIP_DIRS and not p.name.startswith(".")) or p.name in {".github", ".agent", ".claude"})]

    def walk(path: Path, depth: int) -> None:
        if len(entries) >= max_entries or depth > max_depth:
            return
        children = visible_children(path)
        for idx, child in enumerate(children):
            if len(entries) >= max_entries:
                break
            prefix = "  " * depth + ("└─ " if idx == len(children) - 1 else "├─ ")
            name = child.name + ("/" if child.is_dir() else "")
            entries.append(prefix + name)
            if child.is_dir():
                walk(child, depth + 1)
    entries.append(repo.name + "/")
    walk(repo, 1)
    return entries


def git_snapshot(repo: Path) -> dict:
    ok_root, root = run_git(repo, ["rev-parse", "--show-toplevel"])
    ok_branch, branch = run_git(repo, ["branch", "--show-current"])
    ok_status, status = run_git(repo, ["status", "--short"])
    ok_log, log = run_git(repo, ["log", "--oneline", "-8"])
    ok_log_full, log_full = run_git(repo, ["log", "--format=%h %s%n%b----ENDCOMMIT----", "-5"])
    ok_diff, diff = run_git(repo, ["diff", "--stat"])
    ok_remote, remote = run_git(repo, ["remote", "get-url", "origin"])
    ok_stash, stash = run_git(repo, ["stash", "list"])
    return {
        "is_git_repo": ok_root,
        "root": root if ok_root else "unknown",
        "branch": branch if ok_branch and branch else "unknown",
        "status_short": status if ok_status else "",
        "recent_commits": log.splitlines() if ok_log and log else [],
        "recent_commit_bodies": log_full if ok_log_full else "",
        "diff_stat": diff if ok_diff else "",
        "remote": remote if ok_remote else "",
        "stash": stash.splitlines() if ok_stash and stash else [],
    }


def infer_objective(records: list[SourceRecord], parsed: dict) -> tuple[str, str]:
    for key in ["objective", "current_objective", "goal", "task", "current_goal"]:
        val = parsed.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip(), ".agent/context.json"
    priority_files = ["TASK_STATE.md", ".agent/handoff.md", "HANDOFF.md", "CONTEXT.md", "memory-bank/activeContext.md", "README.md"]
    by_path = {r.path: r for r in records}
    for p in priority_files:
        rec = by_path.get(p)
        if rec and rec.exists and rec.summary:
            return rec.summary.split(";")[0].strip(), p
    gstack = next((r for r in records if r.kind == "gstack-artifact" and r.summary), None)
    if gstack:
        return gstack.summary.split(";")[0].strip(), gstack.path
    return "未找到明确当前目标。请从下一步行动、Git 状态和用户请求中恢复上下文。", "inferred"


def list_from_parsed(parsed: dict, keys: Iterable[str]) -> list[str]:
    for key in keys:
        val = parsed.get(key)
        if isinstance(val, list):
            out = []
            for item in val:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    text = item.get("action") or item.get("text") or item.get("decision") or item.get("summary") or str(item)
                    out.append(str(text))
            if out:
                return out[:8]
        if isinstance(val, str) and val.strip():
            return [val.strip()]
    return []


def infer_commands(repo: Path) -> list[str]:
    cmds: list[str] = []
    pkg = repo / "package.json"
    package_runner = "npm run"
    if (repo / "pnpm-lock.yaml").exists():
        package_runner = "pnpm"
    elif (repo / "yarn.lock").exists():
        package_runner = "yarn"
    if pkg.exists():
        try:
            data = json.loads(read_text(pkg))
            scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
            for name in ["test", "lint", "typecheck", "build", "dev"]:
                if name in scripts:
                    cmds.append(f"{package_runner} {name}" if package_runner != "npm run" else f"npm run {name}")
        except Exception:
            pass
    if (repo / "pyproject.toml").exists():
        cmds.extend(["python -m pytest", "python -m ruff check ."])
    if (repo / "Cargo.toml").exists():
        cmds.extend(["cargo test", "cargo clippy"])
    if (repo / "go.mod").exists():
        cmds.extend(["go test ./..."])
    if (repo / "Makefile").exists():
        cmds.append("make test")
    seen: set[str] = set()
    unique: list[str] = []
    for cmd in cmds:
        if cmd not in seen:
            unique.append(cmd)
            seen.add(cmd)
    return unique[:10]


def changed_files(status_short: str) -> list[str]:
    files = []
    for line in status_short.splitlines():
        if not line.strip():
            continue
        files.append(line[3:].strip() if len(line) > 3 else line.strip())
    return files[:40]


def source_confidence(records: list[SourceRecord], git: dict, parsed: dict) -> tuple[str, list[str]]:
    found = {r.path for r in records if r.exists}
    reasons = []
    score = 0
    if git.get("is_git_repo"):
        score += 2
        reasons.append("Git 元数据可用")
    if "TASK_STATE.md" in found or ".agent/context.json" in found:
        score += 3
        reasons.append("找到明确任务状态")
    if ".agent/handoff.md" in found or "HANDOFF.md" in found or any(r.kind in {"run-note", "gstack-artifact"} for r in records):
        score += 2
        reasons.append("找到 handoff、run 或 review 工件")
    if "AGENTS.md" in found or "CLAUDE.md" in found:
        score += 1
        reasons.append("找到 agent 指令")
    if parsed:
        score += 1
        reasons.append("已解析机器可读上下文")
    if score >= 7:
        return "high", reasons
    if score >= 3:
        return "medium", reasons
    return "low", reasons or ["明确上下文较少"]


def make_decision_gates(git: dict, state_bits: dict) -> list[str]:
    gates: list[str] = []
    if state_bits["objective_source"] == "inferred":
        gates.append("未找到明确当前目标时，先停下并询问用户是否期望继续实现。")
    if git.get("status_short"):
        gates.append("存在未提交改动时，先确认来源和意图，再进行大范围编辑。")
    if state_bits["confidence"] == "low":
        gates.append("上下文置信度较低时，执行破坏性改动前必须停下确认。")
    if state_bits["missing_state"]:
        gates.append("多步骤工作开始前，询问是否初始化 TASK_STATE.md 或 .agent/context.json。")
    if state_bits["commands"] and not state_bits["tests_run"]:
        gates.append("至少一个列出的验证命令成功运行前，不要声称验证通过。")
    if not gates:
        gates.append("未检测到强制停止条件；编辑关键文件前仍需核对来源审计。")
    return gates[:8]


def make_completion_status(risks: list[str], missing: list[str], confidence: str) -> dict:
    if confidence == "low" and missing:
        status = "NEEDS_CONTEXT"
        reason = "仪表盘已生成，但明确的 handoff 或状态来源缺失或较少。"
    elif risks or missing:
        status = "DONE_WITH_CONCERNS"
        reason = "仪表盘已生成，但缺失来源或风险需要在实现前复核。"
    else:
        status = "DONE"
        reason = "仪表盘已根据明确状态来源和 Git 信号生成。"
    return {
        "status": status,
        "reason": reason,
        "attempted": ["generate_context_dashboard.py", "静态来源扫描", "可用时读取 Git 快照"],
        "recommendation": "运行 validate_context_dashboard.py，复核停止与确认条件，并在下一次 agent 执行后更新状态文件。",
    }


def make_state(repo: Path) -> dict:
    git = git_snapshot(repo)
    records, parsed = collect_sources(repo, git.get("remote", ""))
    objective, objective_source = infer_objective(records, parsed)
    next_actions = list_from_parsed(parsed, ["next_actions", "next_steps", "todo", "todos", "remaining"])
    blockers = list_from_parsed(parsed, ["blockers", "risks", "open_questions", "unresolved"])
    tests_run = list_from_parsed(parsed, ["tests_run", "validation_run", "checks_run"])
    tests_not_run = list_from_parsed(parsed, ["tests_not_run", "validation_not_run", "checks_not_run"])
    commands = infer_commands(repo)
    cfiles = changed_files(git.get("status_short", ""))
    confidence, confidence_reasons = source_confidence(records, git, parsed)
    missing = [r.path for r in records if not r.exists and r.path in SOURCE_CANDIDATES]
    used = [asdict(r) for r in records if r.exists]

    if not next_actions:
        next_actions = ["编辑前先向用户或任务记录确认当前目标。"]
        if cfiles:
            next_actions.append("检查未提交改动，并决定继续、测试或请求处理。")
        next_actions.append("下一次工作结束后更新 TASK_STATE.md 或 .agent/context.json。")
    if not blockers:
        blockers = ["状态文件中未找到明确阻塞项；这表示未知，不表示没有阻塞。"]
    if not tests_not_run and commands:
        tests_not_run = [f"本生成器未验证：{cmd}" for cmd in commands[:4]]

    found_paths = {r.path for r in records if r.exists}
    missing_state = not any(p in found_paths for p in ["TASK_STATE.md", ".agent/context.json", ".agent/handoff.md", "HANDOFF.md", "CONTEXT.md"])
    risks: list[str] = []
    if missing_state:
        risks.append("未找到明确任务状态或 handoff 文件；仪表盘包含推断状态。")
    if git.get("status_short"):
        risks.append("工作区存在未提交改动；下一个 agent 大范围编辑前必须检查。")
    if git.get("stash"):
        risks.append("存在 Git stash 条目；其中可能包含暂停中的相关工作。")
    if not git.get("is_git_repo"):
        risks.append("Git 元数据不可用；最近改动和分支信息可能不完整。")
    if not commands:
        risks.append("未从常见项目 manifest 中推断出验证命令。")

    state_bits = {
        "objective_source": objective_source,
        "confidence": confidence,
        "missing_state": missing_state,
        "commands": commands,
        "tests_run": tests_run,
    }
    decision_gates = make_decision_gates(git, state_bits)
    completion_status = make_completion_status(risks, missing, confidence)

    return {
        "schema_version": "1.1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repo": repo.name,
        "repo_path": repo.as_posix(),
        "remote": git.get("remote", ""),
        "branch": git.get("branch", "unknown"),
        "status": "dirty" if git.get("status_short") else ("clean" if git.get("is_git_repo") else "unknown"),
        "confidence": confidence,
        "confidence_reasons": confidence_reasons,
        "objective": objective,
        "objective_source": objective_source,
        "next_actions": next_actions[:8],
        "blockers": blockers[:8],
        "changed_files": cfiles,
        "important_files": [r["path"] for r in used if r["kind"] in {"agent-state", "agent-instructions", "memory-bank", "gstack-artifact"}][:24],
        "tests_run": tests_run[:10],
        "tests_not_run": tests_not_run[:10],
        "commands": commands,
        "risks": risks[:10],
        "decision_gates": decision_gates,
        "completion_status": completion_status,
        "context_health": {
            "confidence": confidence,
            "sources_used_count": len(used),
            "sources_missing_count": len(missing),
            "missing_state": missing_state,
            "dirty_tree": bool(git.get("status_short")),
            "gstack_artifacts_count": sum(1 for r in used if r["kind"] == "gstack-artifact"),
        },
        "recent_commits": git.get("recent_commits", []),
        "git_stash": git.get("stash", []),
        "diff_stat": git.get("diff_stat", ""),
        "repo_tree": repo_tree(repo),
        "sources_used": used,
        "sources_missing": missing,
    }


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def list_items(items: list[str], empty: str) -> str:
    if not items:
        return f"<li class='empty'>{esc(empty)}</li>"
    return "".join(f"<li>{esc(item)}</li>" for item in items)


def table_rows(rows: list[list[str]], empty: str, cols: int) -> str:
    if not rows:
        return f"<tr><td colspan='{cols}' class='empty'>{esc(empty)}</td></tr>"
    return "".join("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows)


def render_html(state: dict) -> str:
    sources = state["sources_used"]
    source_rows = [[s["path"], s["kind"], s.get("summary", ""), s.get("mtime", "")] for s in sources]
    file_rows = [[p, "已变更", "编辑前先检查"] for p in state["changed_files"]]
    file_rows += [[p, "事实源", "Agent、memory 或 gstack 来源"] for p in state["important_files"] if p not in state["changed_files"]]
    action_rows = [[str(i + 1), a, "恢复安全性", state.get("objective_source", "inferred"), "中", "已记录或已验证"] for i, a in enumerate(state["next_actions"])]
    blockers = [[b, "未知", "阻塞" if "未找到明确" not in b else "未知"] for b in state["blockers"]]
    command_rows = [[cmd, "推断命令", "生成器未运行"] for cmd in state["commands"]]
    health = state["context_health"]
    health_rows = [[k.replace("_", " "), str(v)] for k, v in health.items()]
    completion = state["completion_status"]
    completion_rows = [
        ["状态", completion.get("status", "unknown")],
        ["原因", completion.get("reason", "")],
        ["已尝试", "; ".join(completion.get("attempted", []))],
        ["建议", completion.get("recommendation", "")],
    ]

    resume_prompt = (
        "先阅读 context/index.html 和 context/context-state.json。"
        "再从下一步行动列表继续。编辑前确认阻塞项、已变更文件、验证命令和停止条件。"
        "结束时更新 TASK_STATE.md 或 .agent/context.json，并重新生成本仪表盘。"
    )
    tree_text = "\n".join(state["repo_tree"])
    commits_text = "\n".join(state["recent_commits"]) or "没有可用的最近提交。"
    diff_text = state["diff_stat"] or "没有可用的 diff 统计。"

    return f"""<!doctype html>
<html lang="zh-CN" data-mode="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(state['repo'])} agent 交接仪表盘</title>
  <link rel="stylesheet" href="assets/site.css">
</head>
<body>
  <a class="skip-link" href="#main">跳到正文</a>
  <header class="topbar">
    <div>
      <p class="eyebrow">agent 交接仪表盘</p>
      <h1>{esc(state['repo'])}</h1>
    </div>
    <nav aria-label="章节">
      <a href="#start-here">起步</a>
      <a href="#next-actions">下一步</a>
      <a href="#decision-gates">停止条件</a>
      <a href="#sources">来源</a>
      <button type="button" id="mode-toggle">切换主题</button>
    </nav>
  </header>
  <main id="main">
    <section id="resume" class="hero panel">
      <div>
        <p class="eyebrow">恢复摘要</p>
        <h2>{esc(state['objective'])}</h2>
        <p class="lead">目标来源：<code>{esc(state['objective_source'])}</code>。生成时间：{esc(state['generated_at'])}。</p>
      </div>
      <div class="status-grid" aria-label="状态摘要">
        <div><span>分支</span><strong>{esc(state['branch'])}</strong></div>
        <div><span>工作区</span><strong>{esc(state['status'])}</strong></div>
        <div><span>置信度</span><strong>{esc(state['confidence'])}</strong></div>
        <div><span>完成状态</span><strong>{esc(completion.get('status','unknown'))}</strong></div>
      </div>
    </section>

    <section id="start-here" class="panel">
      <div class="section-head"><p class="eyebrow">Agent 起步说明</p><h2>恢复指令 <span class="machine-label">Agent start-here</span></h2></div>
      <div class="copy-box"><pre><code id="resume-prompt">{esc(resume_prompt)}</code></pre><button type="button" data-copy="resume-prompt">复制提示词</button></div>
      <ul class="inline-list">{list_items(state['confidence_reasons'], '未记录置信度原因。')}</ul>
    </section>

    <section id="next-actions" class="panel">
      <div class="section-head"><p class="eyebrow">按恢复价值排序</p><h2>下一步行动 <span class="machine-label">Next actions</span></h2></div>
      <div class="table-wrap"><table><thead><tr><th>#</th><th>行动</th><th>原因</th><th>来源</th><th>风险</th><th>完成信号</th></tr></thead><tbody>{table_rows(action_rows, '未找到下一步行动。', 6)}</tbody></table></div>
    </section>

    <section id="blockers" class="panel">
      <div class="section-head"><p class="eyebrow">不要跳过</p><h2>阻塞项与开放问题 <span class="machine-label">Blockers and open questions</span></h2></div>
      <div class="table-wrap"><table><thead><tr><th>事项</th><th>负责人</th><th>级别</th></tr></thead><tbody>{table_rows(blockers, '未记录阻塞项。', 3)}</tbody></table></div>
    </section>

    <section id="decision-gates" class="panel">
      <div class="section-head"><p class="eyebrow">停止条件</p><h2>停止与确认条件 <span class="machine-label">Decision gates</span></h2></div>
      <p>遇到以下条件时，下一个 agent 应先询问，而不是静默继续。</p>
      <ul class="risk-list">{list_items(state['decision_gates'], '未检测到停止条件。')}</ul>
    </section>

    <section id="files" class="panel">
      <div class="section-head"><p class="eyebrow">改动表面</p><h2>已变更与重要文件 <span class="machine-label">Changed and important files</span></h2></div>
      <div class="table-wrap"><table><thead><tr><th>路径</th><th>类型</th><th>为什么重要</th></tr></thead><tbody>{table_rows(file_rows, '未找到已变更或重要文件。', 3)}</tbody></table></div>
    </section>

    <section id="repo-map" class="panel split">
      <div><div class="section-head"><p class="eyebrow">有界扫描</p><h2>项目结构树 <span class="machine-label">Repo map</span></h2></div><pre class="tree"><code>{esc(tree_text)}</code></pre></div>
      <div><div class="section-head"><p class="eyebrow">Git 信号</p><h2>最近活动</h2></div><h3>最近提交</h3><pre><code>{esc(commits_text)}</code></pre><h3>Diff 统计</h3><pre><code>{esc(diff_text)}</code></pre></div>
    </section>

    <section id="handoff" class="panel">
      <div class="section-head"><p class="eyebrow">交接记录</p><h2>Handoff 记录 <span class="machine-label">Handoff ledger</span></h2></div>
      <p>下面列出最新 agent 状态、运行记录、memory-bank 文件、gstack 工件和指令文件。缺失的预期 handoff 文件表示状态缺口。</p>
      <ul>{list_items([s['path'] + ' — ' + s.get('summary','') for s in sources if s['kind'] in {'agent-state','run-note','memory-bank','gstack-artifact'}], '未找到明确 handoff、gstack 工件或 memory 记录。')}</ul>
    </section>

    <section id="validation" class="panel">
      <div class="section-head"><p class="eyebrow">验证检查</p><h2>验证命令与结果 <span class="machine-label">Validation and commands</span></h2></div>
      <div class="table-wrap"><table><thead><tr><th>命令</th><th>依据</th><th>状态</th></tr></thead><tbody>{table_rows(command_rows, '未推断出命令。', 3)}</tbody></table></div>
      <h3>已运行测试</h3><ul>{list_items(state['tests_run'], '来源中未找到测试通过或失败证据。')}</ul>
      <h3>未运行测试</h3><ul>{list_items(state['tests_not_run'], '未明确记录缺失验证。')}</ul>
    </section>

    <section id="risks" class="panel">
      <div class="section-head"><p class="eyebrow">安全</p><h2>风险 <span class="machine-label">Risks</span></h2></div>
      <ul class="risk-list">{list_items(state['risks'], '未检测到风险；大改前仍需人工复核。')}</ul>
    </section>

    <section id="context-health" class="panel">
      <div class="section-head"><p class="eyebrow">恢复信号</p><h2>上下文健康度 <span class="machine-label">Context health</span></h2></div>
      <div class="table-wrap"><table><thead><tr><th>信号</th><th>值</th></tr></thead><tbody>{table_rows(health_rows, '未生成上下文健康度数据。', 2)}</tbody></table></div>
    </section>

    <section id="completion-status" class="panel">
      <div class="section-head"><p class="eyebrow">流程状态</p><h2>完成状态 <span class="machine-label">Completion status</span></h2></div>
      <div class="table-wrap"><table><thead><tr><th>字段</th><th>值</th></tr></thead><tbody>{table_rows(completion_rows, '未生成完成状态。', 2)}</tbody></table></div>
    </section>

    <section id="sources" class="panel">
      <div class="section-head"><p class="eyebrow">审计链路</p><h2>来源审计 <span class="machine-label">Source audit</span></h2></div>
      <div class="table-wrap"><table><thead><tr><th>路径</th><th>类型</th><th>摘要</th><th>修改时间</th></tr></thead><tbody>{table_rows(source_rows, '未读取来源文件。', 4)}</tbody></table></div>
      <details><summary>缺失的预期来源</summary><ul>{list_items(state['sources_missing'], '没有缺失的预期来源文件。')}</ul></details>
    </section>
  </main>
  <footer><p>静态仪表盘。每次 agent 交接或仓库状态发生有意义变化后都应重新生成。</p></footer>
  <script src="assets/site.js"></script>
</body>
</html>
"""


def css() -> str:
    return """:root{--bg:#f7f4ef;--surface:#fffdf8;--text:#1e252b;--muted:#5d6873;--line:#d8d0c4;--brand:#355c7d;--brand-contrast:#ffffff;--warn:#8a4b00;--danger:#8a1f1f;--ok:#236b4e;--shadow:0 18px 40px rgba(30,37,43,.08);--radius:18px;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;--sans:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}html[data-mode="dark"]{--bg:#111820;--surface:#17212b;--text:#eef3f7;--muted:#a8b4bf;--line:#2d3b48;--brand:#7fb4d8;--brand-contrast:#081018;--shadow:0 18px 40px rgba(0,0,0,.24)}*{box-sizing:border-box}body{margin:0;background:linear-gradient(135deg,var(--bg),#ece7dd);color:var(--text);font-family:var(--sans);line-height:1.55}a{color:inherit}.skip-link{position:absolute;left:-999px}.skip-link:focus{left:16px;top:12px;background:var(--brand);color:var(--brand-contrast);padding:.6rem;border-radius:.5rem;z-index:10}.topbar{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;gap:1rem;align-items:center;padding:1rem clamp(1rem,3vw,2rem);background:rgba(255,253,248,.84);backdrop-filter:blur(16px);border-bottom:1px solid var(--line)}html[data-mode="dark"] .topbar{background:rgba(17,24,32,.86)}.topbar h1{margin:.1rem 0 0;font-size:clamp(1.35rem,3vw,2.3rem)}nav{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center}nav a,button{border:1px solid var(--line);background:var(--surface);color:var(--text);padding:.55rem .75rem;border-radius:999px;text-decoration:none;font:inherit;cursor:pointer}.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:.72rem;font-weight:800;color:var(--brand);margin:0 0 .35rem}.machine-label{display:inline-block;margin-left:.35rem;color:var(--muted);font-size:.78rem;font-weight:700}.lead{font-size:1.04rem;color:var(--muted);max-width:76ch}main{width:min(1180px,calc(100% - 2rem));margin:1.4rem auto 4rem;display:grid;gap:1rem}.panel{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:clamp(1rem,2.4vw,1.7rem)}.hero{display:grid;grid-template-columns:1.4fr .9fr;gap:1rem;align-items:stretch}.hero h2{font-size:clamp(1.5rem,4vw,3.1rem);line-height:1.06;margin:.2rem 0}.status-grid{display:grid;grid-template-columns:1fr 1fr;gap:.7rem}.status-grid div{border:1px solid var(--line);border-radius:14px;padding:.9rem;background:rgba(53,92,125,.07)}.status-grid span{display:block;color:var(--muted);font-size:.82rem}.status-grid strong{display:block;font-size:1.1rem;margin-top:.2rem}.section-head{display:flex;justify-content:space-between;gap:1rem;align-items:end;margin-bottom:.9rem}.section-head h2{margin:0;font-size:1.35rem}.copy-box{display:grid;grid-template-columns:1fr auto;gap:.75rem;align-items:start}.copy-box pre{margin:0}.copy-box button{background:var(--brand);color:var(--brand-contrast);border-color:var(--brand)}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:14px}table{width:100%;border-collapse:collapse;min-width:720px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:.75rem}th{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);background:rgba(53,92,125,.08)}tr:last-child td{border-bottom:0}pre{max-width:100%;overflow:auto;background:rgba(0,0,0,.05);border:1px solid var(--line);padding:.9rem;border-radius:14px}code{font-family:var(--mono);font-size:.9em}.split{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.inline-list,.risk-list{display:grid;gap:.45rem}.empty{color:var(--muted);font-style:italic}details{margin-top:1rem;border:1px solid var(--line);border-radius:14px;padding:.8rem}summary{cursor:pointer;font-weight:700}footer{width:min(1180px,calc(100% - 2rem));margin:0 auto 2rem;color:var(--muted)}@media (max-width:820px){.hero,.split,.copy-box{grid-template-columns:1fr}.topbar{position:static;align-items:flex-start;flex-direction:column}.status-grid{grid-template-columns:1fr}table{min-width:640px}}"""


def js() -> str:
    return """(function(){const root=document.documentElement;const saved=localStorage.getItem('context-dashboard-mode');if(saved){root.setAttribute('data-mode',saved)}const toggle=document.getElementById('mode-toggle');if(toggle){toggle.addEventListener('click',()=>{const next=root.getAttribute('data-mode')==='dark'?'light':'dark';root.setAttribute('data-mode',next);localStorage.setItem('context-dashboard-mode',next);toggle.textContent=next==='dark'?'浅色模式':'深色模式';});}document.querySelectorAll('[data-copy]').forEach((button)=>{button.addEventListener('click',async()=>{const el=document.getElementById(button.getAttribute('data-copy'));if(!el)return;try{await navigator.clipboard.writeText(el.textContent||'');button.textContent='已复制';setTimeout(()=>button.textContent='复制提示词',1200);}catch(e){button.textContent='请手动选择文本';}});});})();"""


def root_redirect() -> str:
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=context/index.html"><title>Agent 交接仪表盘</title></head><body><p><a href="context/index.html">打开 agent 交接仪表盘</a></p></body></html>"""


def write_dashboard(repo: Path, out: Path, make_redirect: bool) -> dict:
    state = make_state(repo)
    out.mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render_html(state), encoding="utf-8")
    (out / "assets" / "site.css").write_text(css(), encoding="utf-8")
    (out / "assets" / "site.js").write_text(js(), encoding="utf-8")
    (out / "context-state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    if make_redirect:
        (out.parent / "context.html").write_text(root_redirect(), encoding="utf-8")
    return state


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="生成静态 coding-agent 交接仪表盘。")
    parser.add_argument("--repo", default=".", help="要扫描的仓库根目录")
    parser.add_argument("--out", default=None, help="输出目录，默认：<repo>/context")
    parser.add_argument("--no-root-redirect", action="store_true", help="不在 context/ 旁写入 context.html 跳转页")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    if not repo.exists() or not repo.is_dir():
        print(f"未找到仓库目录：{repo}", file=sys.stderr)
        return 2
    out = Path(args.out).resolve() if args.out else repo / "context"
    state = write_dashboard(repo, out, not args.no_root_redirect)
    print("已生成 agent 交接仪表盘")
    print(f"HTML：{out / 'index.html'}")
    print(f"JSON：{out / 'context-state.json'}")
    print(f"置信度：{state['confidence']}")
    print(f"完成状态：{state['completion_status']['status']}")
    print(f"已使用来源：{len(state['sources_used'])}")
    print(f"缺失来源：{len(state['sources_missing'])}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
