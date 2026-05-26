"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { apiFetch, AskResponse, SourceMode } from "../../../lib/api";

const modes: SourceMode[] = ["auto", "local_only", "web_only", "hybrid"];

// 渲染统一 Ask 页面。
export default function AskPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [message, setMessage] = useState("/study explain RAG from my notes");
  const [mode, setMode] = useState<SourceMode>("auto");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submitAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await apiFetch<AskResponse>("/ask", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, message, selected_mode: mode }),
      });
      setAnswer(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ask failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell three-pane">
      <aside className="glass-panel sidebar">
        <p className="eyebrow">Project</p>
        <nav className="nav-list">
          <Link href="/app">Projects</Link>
          <Link href={`/app/projects/${projectId}`}>Ask</Link>
          <Link href={`/app/projects/${projectId}/library`}>Library</Link>
          <Link href={`/app/projects/${projectId}/quiz`}>Quiz</Link>
        </nav>
      </aside>

      <section className="glass-panel chat-panel">
        <div className="page-title-row">
          <div>
            <p className="eyebrow">Ask</p>
            <h1>统一问答入口</h1>
          </div>
          {answer && (
            <Link className="secondary-button" href={`/dev/traces/${answer.trace_id}`}>
              Trace
            </Link>
          )}
        </div>
        <form className="ask-form" onSubmit={submitAsk}>
          <textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={5} />
          <div className="toolbar-row">
            <label>
              Mode
              <select value={mode} onChange={(event) => setMode(event.target.value as SourceMode)}>
                {modes.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "生成中..." : "发送"}
            </button>
          </div>
        </form>
        {error && <p className="error-banner">{error}</p>}
        {answer ? (
          <article className="answer-card">
            <div className="sources-header">
              <span>Mode: {answer.mode}</span>
              <span>{answer.sources.local_chunks} local chunks</span>
              <span>{answer.sources.web_pages} web pages</span>
            </div>
            <pre>{answer.answer}</pre>
          </article>
        ) : (
          <div className="empty-state">先在 Library 上传资料并完成解析，然后使用 /study 提问。</div>
        )}
      </section>

      <aside className="glass-panel sources-panel">
        <p className="eyebrow">Sources</p>
        {!answer && <p>回答生成后，这里会显示可展开来源。</p>}
        {answer?.citations.map((citation) => (
          <article className="source-card" key={citation.id}>
            <strong>{citation.source_type}</strong>
            <span>{citation.page_no ? `page ${citation.page_no}` : citation.url}</span>
            <p>{citation.quote}</p>
          </article>
        ))}
      </aside>
    </main>
  );
}
