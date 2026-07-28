// Implements the unified persistent chat with optional web evidence.
"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
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

export default function ResearchChatPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [message, setMessage] = useState("");
  const [webEnabled, setWebEnabled] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [error, setError] = useState<ReturnType<typeof describeApiError> | null>(null);
  const [loading, setLoading] = useState(false);
  const [degraded, setDegraded] = useState(false);

  async function loadMessages(id: string) {
    const body = await apiFetch<{ messages: ConversationMessage[] }>(
      `/conversations/${id}/messages`,
    );
    setMessages(body.messages);
  }

  useEffect(() => {
    let cancelled = false;
    apiFetch<{ items: ConversationSummary[] }>(`/projects/${projectId}/conversations`)
      .then(async (body) => {
        if (cancelled) return;
        setConversations(body.items);
        if (body.items[0]) {
          setConversationId(body.items[0].id);
          await loadMessages(body.items[0].id);
        }
      })
      .catch((requestError) => {
        if (!cancelled) setError(describeApiError(requestError));
      });
    return () => { cancelled = true; };
  }, [projectId]);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = message.trim();
    if (!prompt) return;
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
      setConversationId(answer.conversation_id);
      setDegraded(answer.rerank_degraded);
      setMessage("");
      await loadMessages(answer.conversation_id);
      const list = await apiFetch<{ items: ConversationSummary[] }>(
        `/projects/${projectId}/conversations`,
      );
      setConversations(list.items);
    } catch (requestError) {
      setError(describeApiError(requestError));
    } finally {
      setLoading(false);
    }
  }

  function startNewChat() {
    setConversationId(null);
    setMessages([]);
    setMessage("");
    setError(null);
    setDegraded(false);
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

      <div className="chat-session-bar">
        <label>
          <span className="sr-only">Conversation</span>
          <select
            value={conversationId ?? ""}
            onChange={(event) => {
              const id = event.target.value;
              if (!id) return startNewChat();
              setConversationId(id);
              void loadMessages(id);
            }}
          >
            <option value="">New conversation</option>
            {conversations.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>
        </label>
        <button type="button" onClick={startNewChat}>New chat</button>
      </div>

      <section className="chat-thread" aria-live="polite" aria-label="Conversation">
        {!messages.length && !loading && (
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
            <span aria-hidden="true" />Thinking{webEnabled ? " with web evidence" : ""}…
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
            disabled={loading || !message.trim()}
            aria-label="Send message"
          >
            {loading ? "…" : "Send"}
          </button>
        </div>
      </form>
    </main>
  );
}
