// Implements the primary grounded research conversation against the authenticated Ask API.
"use client";

import { FormEvent, useState } from "react";
import { useParams } from "next/navigation";
import { ProjectNav } from "../../../../components/project-nav";
import { StateNotice } from "../../../../components/state-notice";
import { apiFetch, AskResponse, describeApiError, SourceMode } from "../../../../lib/api";

const STARTERS = [
  "Summarize the strongest claim and its evidence.",
  "Which sources contradict each other?",
  "What should I verify before citing this research?",
];

/** Coordinates a bounded question, retrieval mode, answer, citations, and recoverable request states. */
export default function ResearchChatPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [message, setMessage] = useState(STARTERS[0]);
  const [mode, setMode] = useState<SourceMode>("local_only");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<ReturnType<typeof describeApiError> | null>(null);
  const [loading, setLoading] = useState(false);

  /** Sends one grounded question through the API client while preserving input on recoverable failure. */
  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      setAnswer(await apiFetch<AskResponse>("/ask", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, message: message.trim(), selected_mode: mode }),
      }));
    } catch (requestError) {
      setError(describeApiError(requestError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell workspace-shell chat-workspace">
      <ProjectNav projectId={projectId} current="chat" />
      <header className="chat-heading">
        <span className="chat-heading__mark" aria-hidden="true">✦</span>
        <p className="eyebrow">Grounded research session</p>
        <h1>Ask your evidence</h1>
        <p>ResearchMate searches the source boundary you choose and keeps the supporting excerpts attached to the answer.</p>
      </header>

      <section className="chat-thread" aria-live="polite" aria-label="Research conversation">
        {!answer && !loading && (
          <div className="chat-starters" aria-label="Suggested questions">
            {STARTERS.map((starter) => <button type="button" key={starter} onClick={() => setMessage(starter)}>{starter}</button>)}
          </div>
        )}
        {answer && (
          <>
            <article className="user-message"><span>You</span><p>{message}</p></article>
            <article className="assistant-message">
              <div className="assistant-message__meta"><span>Mode: {answer.mode.replaceAll("_", " ")}</span><span>{answer.sources.local_chunks} local</span><span>{answer.sources.web_pages} web</span><span>Validation: {answer.validation_status}</span></div>
              <p>{answer.answer}</p>
              <div className="citation-list">
                {answer.citations.map((citation, index) => (
                  <details key={citation.id}><summary>[{index + 1}] {citation.source_type === "local_doc" ? `Source${citation.page_no ? ` · page ${citation.page_no}` : ""}` : citation.url || "Web source"}</summary><blockquote>{citation.quote}</blockquote></details>
                ))}
              </div>
            </article>
          </>
        )}
        {loading && <div className="assistant-loading" role="status"><span aria-hidden="true" />Retrieving and validating evidence…</div>}
        {error && <StateNotice state={error} action={<button type="button" onClick={() => setError(null)}>Edit and retry</button>} />}
      </section>

      <form className="chat-composer" onSubmit={submitQuestion}>
        <div className="chat-composer__toolbar">
          <label><span className="sr-only">Source mode</span><select value={mode} onChange={(event) => setMode(event.target.value as SourceMode)}><option value="local_only">Local sources</option><option value="hybrid">Local + web</option><option value="web_only">Web only</option><option value="auto">Automatic</option></select></label>
          <span>Answers remain bounded by the selected source mode.</span>
        </div>
        <div className="chat-composer__input"><label className="sr-only" htmlFor="research-question">Research question</label><textarea id="research-question" rows={2} minLength={3} maxLength={4000} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ask anything about your research…" required /><button className="primary-button" type="submit" disabled={loading || message.trim().length < 3} aria-label="Send research question">{loading ? "…" : "Send"}</button></div>
        <small>Verify critical claims against the attached source excerpts.</small>
      </form>
    </main>
  );
}
