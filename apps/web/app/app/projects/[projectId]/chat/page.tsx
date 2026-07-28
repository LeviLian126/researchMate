// Implements the unified persistent chat with optional web evidence.
"use client";

import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { ProjectNav } from "../../../../components/project-nav";
import { StateNotice } from "../../../../components/state-notice";
import {
  apiFetch,
  AskResponse,
  ConversationMessage,
  ConversationSummary,
  describeApiError,
} from "../../../../lib/api";

const STARTERS = [
  "Summarize the strongest claim and its evidence.",
  "Which sources contradict each other?",
  "What should I verify before citing this research?",
];

/** Supplies the static-render boundary required by query-backed conversation selection. */
export default function ResearchChatPage() {
  return <Suspense fallback={<main className="app-shell"><div className="empty-state" role="status">Loading conversation…</div></main>}><ResearchChatWorkspace /></Suspense>;
}

/** Coordinates one project conversation and its optional web evidence. */
function ResearchChatWorkspace() {
  const params = useParams<{ projectId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = params.projectId;
  const [message, setMessage] = useState("");
  const [webEnabled, setWebEnabled] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [error, setError] = useState<ReturnType<typeof describeApiError> | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [degraded, setDegraded] = useState(false);
  const [slowResponse, setSlowResponse] = useState(false);
  const routeRequest = useRef(0);
  const historyRequest = useRef(0);

  async function loadMessages(id: string) {
    const requestId = ++historyRequest.current;
    setHistoryLoading(true);
    try {
      const body = await apiFetch<{ messages: ConversationMessage[] }>(
        `/conversations/${id}/messages`,
      );
      if (requestId === historyRequest.current) {
        setMessages(body.messages);
      }
    } finally {
      if (requestId === historyRequest.current) {
        setHistoryLoading(false);
      }
    }
  }

  useEffect(() => {
    const requestId = ++routeRequest.current;
    historyRequest.current += 1;
    setHistoryLoading(true);
    setLoading(false);
    setMessages([]);
    const requestedConversation = searchParams.get("conversation");
    if (searchParams.get("new") === "1") {
      setConversationId(null);
      setHistoryLoading(false);
      return () => { routeRequest.current += 1; };
    }
    apiFetch<{ items: ConversationSummary[] }>(`/projects/${projectId}/conversations`)
      .then(async (body) => {
        if (requestId !== routeRequest.current) return;
        const selected = requestedConversation
          ? body.items.find((item) => item.id === requestedConversation)
          : body.items[0];
        if (selected) {
          setConversationId(selected.id);
          await loadMessages(selected.id);
          if (requestId !== routeRequest.current) return;
          if (!requestedConversation) {
            router.replace(`/app/projects/${projectId}/chat?conversation=${selected.id}`);
          }
        } else {
          setConversationId(null);
          setHistoryLoading(false);
        }
      })
      .catch((requestError) => {
        if (requestId === routeRequest.current) {
          setHistoryLoading(false);
          setError(describeApiError(requestError));
        }
      });
    return () => {
      routeRequest.current += 1;
      historyRequest.current += 1;
    };
  }, [projectId, searchParams]);

  useEffect(() => {
    if (!loading) {
      setSlowResponse(false);
      return;
    }
    const timer = window.setTimeout(() => setSlowResponse(true), 12_000);
    return () => window.clearTimeout(timer);
  }, [loading]);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = message.trim();
    if (!prompt || historyLoading) return;
    const requestId = routeRequest.current;
    setError(null);
    setLoading(true);
    try {
      const answer = await apiFetch<AskResponse>("/ask", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          conversation_id: conversationId,
          message: prompt,
          web_enabled: webEnabled,
        }),
      });
      if (requestId !== routeRequest.current) return;
      setConversationId(answer.conversation_id);
      setDegraded(answer.rerank_degraded);
      setMessage("");
      await loadMessages(answer.conversation_id);
      if (requestId !== routeRequest.current) return;
      router.replace(`/app/projects/${projectId}/chat?conversation=${answer.conversation_id}`);
      window.dispatchEvent(new Event("researchmate:sidebar-refresh"));
    } catch (requestError) {
      if (requestId === routeRequest.current) {
        setError(describeApiError(requestError));
      }
    } finally {
      if (requestId === routeRequest.current) {
        setLoading(false);
      }
    }
  }

  return (
    <main className="app-shell workspace-shell chat-workspace">
      <ProjectNav projectId={projectId} current="chat" />
      <header className="chat-heading">
        <span className="chat-heading__mark" aria-hidden="true">✦</span>
        <p className="eyebrow">Conversation · documents when available</p>
        <h1>Ask naturally. Add evidence when you need it.</h1>
        <p>Chat directly, use uploaded documents automatically, or add current web evidence with one switch.</p>
      </header>

      <section className="chat-thread" aria-live="polite" aria-label="Conversation">
        {!messages.length && !loading && !historyLoading && (
          <div className="chat-starters" aria-label="Suggested questions">
            {STARTERS.map((starter) => (
              <button type="button" key={starter} onClick={() => setMessage(starter)}>
                {starter}
              </button>
            ))}
          </div>
        )}
        {messages.map((item) => (
          <article className={item.role === "user" ? "user-message" : "assistant-message"} key={item.id}>
            <span>{item.role === "user" ? "You" : "ResearchMate"}</span>
            <p>{item.content}</p>
            {!!item.citations.length && (
              <div className="citation-list">
                {item.citations.map((citation, index) => (
                  <details key={citation.id}>
                    <summary>
                      [{index + 1}] {citation.source_type === "local_doc"
                        ? `Document${citation.page_no ? ` · page ${citation.page_no}` : ""}`
                        : citation.url || "Web source"}
                    </summary>
                    <blockquote>{citation.quote}</blockquote>
                  </details>
                ))}
              </div>
            )}
          </article>
        ))}
        {loading && (
          <div className="assistant-loading" role="status">
            <span aria-hidden="true" />
            <div>
              Thinking{webEnabled ? " with web evidence" : ""}…
              {slowResponse && <small>The current provider is taking longer than usual. You can keep this page open.</small>}
            </div>
          </div>
        )}
        {error && (
          <StateNotice
            state={error}
            action={<button type="button" onClick={() => setError(null)}>Edit and retry</button>}
          />
        )}
        {degraded && (
          <StateNotice
            state={{
              title: "Evidence ranking used a safe fallback",
              detail: "A ranking provider was unavailable. The run trace records the fallback used for this answer.",
              kind: "warning",
            }}
          />
        )}
      </section>

      <form className="chat-composer" onSubmit={submitQuestion}>
        <div className="chat-composer__toolbar">
          <label className="web-toggle">
            <input
              type="checkbox"
              checked={webEnabled}
              onChange={(event) => setWebEnabled(event.target.checked)}
            />
            <span>Web</span>
          </label>
          <span>{webEnabled ? "Current web evidence is enabled." : "Uploaded documents are used automatically."}</span>
        </div>
        <div className="chat-composer__input">
          <label className="sr-only" htmlFor="research-question">Message</label>
          <textarea
            id="research-question"
            rows={2}
            minLength={1}
            maxLength={8000}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask anything…"
            required
          />
          <button
            className="primary-button"
            type="submit"
            disabled={loading || historyLoading || !message.trim()}
            aria-label="Send message"
          >
            {loading || historyLoading ? "…" : "Send"}
          </button>
        </div>
      </form>
    </main>
  );
}
