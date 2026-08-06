import { useEffect, useRef } from "react";
import {
  ChevronRight,
  FileText,
  Link2,
  Sparkles,
} from "lucide-react";
import {
  emptyPrompts,
  type Citation,
  type ConversationMessage,
} from "@/lib/mock-data";

interface ConversationThreadProps {
  messages: ConversationMessage[];
  isThinking: boolean;
  onSelectPrompt?: (prompt: string) => void;
}

export function ConversationThread({
  messages,
  isThinking,
  onSelectPrompt,
}: ConversationThreadProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isThinking]);

  const isEmpty = messages.length === 0 && !isThinking;

  if (isEmpty) {
    return (
      <div className="scrollbar-thin h-full overflow-y-auto">
        <div className="flex min-h-full flex-col items-center justify-center px-6 py-16">
          <div className="w-full max-w-2xl">
            <div className="mb-8 text-center">
              <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                What can I help with?
              </h1>
              <p className="mt-3 text-muted-foreground">
                Ask anything about your research sources.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              {emptyPrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => onSelectPrompt?.(prompt)}
                  className="group rounded-xl border border-border/60 bg-white/50 p-4 text-left backdrop-blur-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/30 hover:bg-white/70 hover:shadow-lg hover:shadow-primary/5"
                >
                  <Sparkles
                    className="h-4 w-4 text-primary/70 transition-colors group-hover:text-primary"
                    strokeWidth={1.5}
                  />
                  <p className="mt-2.5 text-sm font-medium leading-snug text-foreground">
                    {prompt}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="scrollbar-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <div className="space-y-8">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {isThinking && <ThinkingIndicator />}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ConversationMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-secondary px-4 py-2.5 text-sm leading-relaxed text-secondary-foreground">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[85%]">
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
          {message.content}
        </div>
        {message.citations && message.citations.length > 0 && (
          <Citations citations={message.citations} />
        )}
      </div>
    </div>
  );
}

function Citations({ citations }: { citations: Citation[] }) {
  return (
    <details className="group mt-3">
      <summary className="flex cursor-pointer list-none items-center gap-1 text-xs font-medium text-primary transition-colors hover:text-primary/80">
        <ChevronRight
          className="h-3.5 w-3.5 transition-transform group-open:rotate-90"
          strokeWidth={1.5}
        />
        {citations.length} {citations.length === 1 ? "source" : "sources"}
      </summary>
      <div className="mt-2 space-y-2">
        {citations.map((cite) => (
          <div
            key={cite.id}
            className="rounded-lg border border-border/60 bg-white/50 p-3 backdrop-blur-sm"
          >
            <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              {cite.source_type === "web_page" ? (
                <>
                  <Link2 className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                  {cite.url && (
                    <a
                      href={cite.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="truncate text-primary hover:underline"
                    >
                      {cite.url}
                    </a>
                  )}
                </>
              ) : (
                <span className="flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                  Document{cite.page_no ? ` · p. ${cite.page_no}` : ""}
                </span>
              )}
            </div>
            <p className="mt-1.5 text-xs italic leading-relaxed text-muted-foreground">
              &ldquo;{cite.quote}&rdquo;
            </p>
          </div>
        ))}
      </div>
    </details>
  );
}

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-1.5 py-2">
      <span className="h-2 w-2 animate-[rm-thinking_1.4s_ease-in-out_infinite] rounded-full bg-primary/60" />
      <span className="h-2 w-2 animate-[rm-thinking_1.4s_ease-in-out_infinite] [animation-delay:0.2s] rounded-full bg-primary/60" />
      <span className="h-2 w-2 animate-[rm-thinking_1.4s_ease-in-out_infinite] [animation-delay:0.4s] rounded-full bg-primary/60" />
    </div>
  );
}
