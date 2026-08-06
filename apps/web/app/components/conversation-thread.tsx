// Renders conversation history, citations, loading feedback, and recoverable workspace notices.
import type { RefObject } from "react";
import type { ConversationMessage } from "../lib/api";
import { StateNotice, type NoticeState } from "./state-notice";
import { Loader2 } from "lucide-react";

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
    <section
      className="relative flex-1 min-h-0 overflow-y-auto scrollbar-thin"
      aria-live="polite"
    >
      <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col gap-4 px-4 py-6 sm:px-6">
        {!messages.length && !historyLoading && (
          <div className="flex flex-1 flex-col items-center justify-center px-6 py-16">
            <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              {projectMode ? `Chat in ${projectName ?? "this project"}` : "What can I help with?"}
            </h1>
            <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-3">
              {EMPTY_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => onSelectPrompt(prompt)}
                  className="rounded-xl border border-border/60 bg-white/50 p-4 text-left text-sm text-muted-foreground backdrop-blur-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/30 hover:bg-white/70 hover:text-foreground hover:shadow-lg hover:shadow-primary/5"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {historyLoading && (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground" role="status">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
            Loading conversation
          </div>
        )}

        {messages.map((item) => (
          <article
            key={item.id}
            className={`conversation-message conversation-message--${item.role} ${item.role === "user" ? "flex justify-end" : "flex justify-start"}`}
          >
            <div className="max-w-[85%]">
              {item.role === "user" ? (
                <div className="rounded-2xl rounded-tr-md bg-secondary px-4 py-2.5 text-sm leading-relaxed text-secondary-foreground">
                  {item.content}
                </div>
              ) : (
                <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                  {item.content}
                </div>
              )}
              {!!item.citations.length && (
                <div className="mt-2 space-y-2">
                  {item.citations.map((citation, index) => (
                    <details
                      key={citation.id}
                      className="rounded-lg border border-border/60 bg-white/50 p-3 backdrop-blur-sm"
                    >
                      <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
                        {index + 1}. {citation.source_type === "web_page"
                          ? citation.url || "Web source"
                          : `Project source${citation.page_no ? `, page ${citation.page_no}` : ""}`}
                      </summary>
                      <blockquote className="mt-2 border-l-2 border-primary/30 pl-3 text-xs italic text-muted-foreground">
                        {citation.quote}
                      </blockquote>
                    </details>
                  ))}
                </div>
              )}
            </div>
          </article>
        ))}

        {sending && (
          <div className="flex items-center gap-1.5 py-3" role="status">
            <span className="h-2 w-2 rounded-full bg-primary/60 animate-[rm-thinking_1.4s_ease-in-out_infinite]" />
            <span className="h-2 w-2 rounded-full bg-primary/60 animate-[rm-thinking_1.4s_ease-in-out_infinite] [animation-delay:0.2s]" />
            <span className="h-2 w-2 rounded-full bg-primary/60 animate-[rm-thinking_1.4s_ease-in-out_infinite] [animation-delay:0.4s]" />
            {slowResponse && (
              <small className="ml-2 text-xs text-muted-foreground">
                Still working. Free providers can take a little longer.
              </small>
            )}
          </div>
        )}

        {error && (
          <StateNotice
            state={error}
            action={
              <button
                type="button"
                onClick={onDismissError}
                className="rounded-md px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-secondary"
              >
                Dismiss
              </button>
            }
          />
        )}

        {degradedNotice && (
          <p
            className="rounded-lg border border-border/60 bg-white/50 px-3 py-2 text-xs text-muted-foreground backdrop-blur-sm"
            role="status"
          >
            Evidence ranking fallback: {degradedNotice}
          </p>
        )}

        <div ref={threadEnd} />
      </div>
    </section>
  );
}
