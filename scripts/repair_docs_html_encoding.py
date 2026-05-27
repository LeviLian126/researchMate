from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

DOC_LEADS = {
    "api-spec.html": "定义前后端 API 契约、校验边界与非实现范围。",
    "db-schema.html": "定义核心库表、RLS、Qdrant payload 与数据生命周期。",
    "execution-plan.html": "multi-agent 模块拆分、边界、验收标准与并行策略。",
    "project-development-process.html": "定义从需求冻结到上线复盘的项目开发流程。",
    "researchmate-architecture.html": "定义系统分层、数据流、安全边界与本地开发环境。",
    "researchmate-prd.html": "定义产品目标、用户范围、MVP 边界与验收标准。",
    "ui-page-spec.html": "定义核心页面、Trace 可见性与 UI 验收边界。",
}

SHARED_STYLE = '<link rel="stylesheet" href="handoff/assets/site.css">'


# 修复通用文档页里被替换为问号的导航、目录和摘要文案。
def repair_common_wrappers() -> None:
    for path in DOCS.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        text = re.sub(
            r'(<a href="(?:\.\./)?HANDOFF\.html"(?: aria-current="page")?>)\?{2,}(</a>)',
            r"\1总览\2",
            text,
        )
        text = re.sub(r"<strong>\?{2,}</strong>", "<strong>目录</strong>", text)
        text = re.sub(
            r"<summary>\?{2,}\s*Markdown\s*\?{2,}</summary>",
            "<summary>原始 Markdown 备份</summary>",
            text,
        )
        if path.name in DOC_LEADS:
            text = re.sub(
                r'<p class="lead">.*?</p>',
                f'<p class="lead">{DOC_LEADS[path.name]}</p>',
                text,
                count=1,
                flags=re.DOTALL,
            )
        path.write_text(text, encoding="utf-8", newline="\n")


# 统一 docs 根页面样式入口，避免继续保留每页一套内联 CSS。
def unify_shared_styles() -> None:
    for path in DOCS.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"\n?\s*<style>.*?</style>", f"\n  {SHARED_STYLE}", text, flags=re.DOTALL)
        if SHARED_STYLE not in text:
            text = text.replace("</head>", f"  {SHARED_STYLE}\n</head>")
        if 'href="progress.html"' not in text:
            text = text.replace(
                '<a href="handoff/index.html">Agent Dashboard</a>',
                '<a href="handoff/index.html">Agent Dashboard</a><a href="progress.html">Progress</a>',
            )
        path.write_text(text, encoding="utf-8", newline="\n")


# 执行所有文档乱码修复任务。
def main() -> None:
    repair_common_wrappers()
    unify_shared_styles()


if __name__ == "__main__":
    main()
