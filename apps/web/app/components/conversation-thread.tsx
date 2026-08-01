// Renders conversation history, citations, loading feedback, and recoverable workspace notices.
import type { RefObject } from "react";
import type { ConversationMessage } from "../lib/api";
import { StateNotice, type NoticeState } from "./state-notice";

interface ConversationThreadProps {
  messages: ConversationMessage[];
  historyLoading: boolean;
  sending: boolean;
  slowResponse: boolean;
  error: NoticeState | null;
  degradedNotice: string | null;
  projectMode: boolean;
  projectName?: string;
  threadEnd: RefObject<HTMLDivElement | null>;
  onDismissError: () => void;
  onSelectPrompt: (prompt: string) => void;
}

const EMPTY_PROMPTS = [
  "Summarize the material and identify its strongest claim.",
  "What assumptions should I verify?",
  "Turn these ideas into a clear research plan.",
];

/** Presents the complete read-only thread state and starter actions. */
export function ConversationThread({
  messages,
  historyLoading,
  sending,
  slowResponse,
  error,
  degradedNotice,
  projectMode,
  projectName,
  threadEnd,
  onDismissError,
  onSelectPrompt,
}: ConversationThreadProps) {
  return (
    <section className="conversation-thread" aria-live="polite">
      {!messages.length && !historyLoading && (
        <div className="conversation-empty">
          <h1>{projectMode ? `Chat in ${projectName ?? "this project"}` : "What can I help with?"}</h1>
          <div>
            {EMPTY_PROMPTS.map((prompt) => (
              <button key={prompt} type="button" onClick={() => onSelectPrompt(prompt)}>
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}
      {historyLoading && <div className="message-skeleton" role="status">Loading conversation</div>}
      {messages.map((item) => (
        <article className={`conversation-message conversation-message--${item.role}`} key={item.id}>
          <div className="conversation-message__body">{item.content}</div>
          {!!item.citations.length && (
            <div className="conversation-citations">
              {item.citations.map((citation, index) => (
                <details key={citation.id}>
                  <summary>
                    {index + 1}. {citation.source_type === "web_page"
                      ? citation.url || "Web source"
                      : `Project source${citation.page_no ? `, page ${citation.page_no}` : ""}`}
                  </summary>
                  <blockquote>{citation.quote}</blockquote>
                </details>
              ))}
            </div>
          )}
        </article>
      ))}
      {sending && (
        <div className="conversation-thinking" role="status">
          <span /><span /><span />
          {slowResponse && <small>Still working. Free providers can take a little longer.</small>}
        </div>
      )}
      {error && (
        <StateNotice
          state={error}
          action={<button type="button" onClick={onDismissError}>Dismiss</button>}
        />
      )}
      {degradedNotice && (
        <p className="conversation-degraded" role="status">
          Evidence ranking fallback: {degradedNotice}
        </p>
      )}
      <div ref={threadEnd} />
    </section>
  );
}
