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


# 复用现有样式并重建根 HANDOFF 页面，避免保留任何乱码片段。
def rebuild_root_handoff() -> None:
    handoff = DOCS / "HANDOFF.html"
    previous = handoff.read_text(encoding="utf-8")
    style_match = re.search(r"<style>\n?(.*?)\n?</style>", previous, flags=re.DOTALL)
    style = style_match.group(1) if style_match else ""

    handoff.write_text(
        f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ResearchMate Handoff</title>
  <style>
{style}
</style>
</head>
<body>
  <header class="top">
    <div class="top-inner">
      <a class="brand" href="HANDOFF.html">ResearchMate Docs</a>
      <nav class="nav" aria-label="Project documentation">
        <a href="HANDOFF.html" aria-current="page">总览</a>
        <a href="handoff/index.html">Agent Dashboard</a>
        <a href="researchmate-prd.html">PRD</a>
        <a href="researchmate-architecture.html">Architecture</a>
        <a href="project-development-process.html">Process</a>
        <a href="api-spec.html">API</a>
        <a href="openapi-spec.html">OpenAPI</a>
        <a href="db-schema.html">DB</a>
        <a href="ui-page-spec.html">UI</a>
        <a href="execution-plan.html">Plan</a>
      </nav>
    </div>
  </header>
  <main class="wrap">
    <section class="hero">
      <span class="eyebrow">Agent-friendly HTML documentation</span>
      <h1>ResearchMate Handoff</h1>
      <p class="lead">项目已将 docs 内 Markdown 文档迁移为 HTML 页面，并补齐可导航的 HTML、agent 交接上下文和 multi-agent 交付计划。</p>
      <div class="chip">Status: DONE_WITH_CONCERNS</div>
      <div class="chip">Docs Markdown: migrated</div>
      <div class="chip">Source preservation: raw Markdown embedded</div>
    </section>
    <section class="doc">
      <h2 id="start">文档入口</h2>
      <p>后续 agent 应先阅读 <a href="handoff/index.html">Agent Dashboard</a>，再按页眉进入 PRD、Architecture、API、DB、UI 与 Execution Plan。</p>
      <div class="cards">
        <article class="card"><h3>Agent Dashboard</h3><p>当前任务状态、下一步行动、风险和 source audit。</p><p><a href="handoff/index.html">打开</a></p></article>
        <article class="card"><h3>PRD</h3><p>产品目标、用户范围和 MVP 成功标准。</p><p><a href="researchmate-prd.html">打开</a></p></article>
        <article class="card"><h3>Architecture</h3><p>系统边界、服务分层、RAG、Trace 与安全策略。</p><p><a href="researchmate-architecture.html">打开</a></p></article>
        <article class="card"><h3>Process</h3><p>阶段化研发流程和每阶段验收口径。</p><p><a href="project-development-process.html">打开</a></p></article>
        <article class="card"><h3>API Spec</h3><p>HTTP API、错误模型、请求响应和校验边界。</p><p><a href="api-spec.html">打开</a></p></article>
        <article class="card"><h3>OpenAPI</h3><p>机器可读 OpenAPI 契约的 HTML 镜像。</p><p><a href="openapi-spec.html">打开</a></p></article>
        <article class="card"><h3>DB Schema</h3><p>Postgres、RLS、Qdrant payload 与删除策略。</p><p><a href="db-schema.html">打开</a></p></article>
        <article class="card"><h3>UI Page Spec</h3><p>Ask、Library、Quiz、Trace 的页面约定。</p><p><a href="ui-page-spec.html">打开</a></p></article>
        <article class="card"><h3>Execution Plan</h3><p>multi-agent 分工、边界与交付标准。</p><p><a href="execution-plan.html">打开</a></p></article>
      </div>
      <h2 id="policy">文档维护规则</h2>
      <blockquote>项目文档以后优先维护 HTML 页面，避免在 docs 内新增 Markdown。</blockquote>
      <ul>
        <li>保持 <code>docs</code> 目录无 Markdown。</li>
        <li>机器可读契约放在 <code>infra</code> 等工程目录，<code>docs</code> 内只保留 HTML 阅读页。</li>
        <li>交接信息同步维护 <code>docs/handoff/index.html</code> 与 <code>docs/handoff/context-state.json</code>。</li>
      </ul>
    </section>
  </main>
</body>
</html>
""",
        encoding="utf-8",
        newline="\n",
    )


# 执行所有文档乱码修复任务。
def main() -> None:
    repair_common_wrappers()
    rebuild_root_handoff()
    repair_common_wrappers()


if __name__ == "__main__":
    main()
