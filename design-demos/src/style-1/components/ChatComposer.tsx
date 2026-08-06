import { ArrowUp, Globe, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";

interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  webEnabled: boolean;
  onToggleWeb: () => void;
}

export function ChatComposer({
  value,
  onChange,
  onSend,
  webEnabled,
  onToggleWeb,
}: ChatComposerProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="px-4 pb-4 pt-2 sm:px-6">
      <div className="mx-auto max-w-3xl">
        {/* Glass composer — scale-in on focus is the signature move */}
        <div className="rounded-2xl border border-white/30 bg-white/70 shadow-lg shadow-primary/5 backdrop-blur-xl transition-all duration-300 ease-out focus-within:scale-[1.01] focus-within:shadow-xl focus-within:shadow-primary/10">
          <Textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your research…"
            rows={1}
            className="max-h-[200px] resize-none border-0 bg-transparent px-4 pb-1 pt-3.5 text-sm shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
          />
          <div className="flex items-center justify-between px-3 pb-3 pt-1">
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                aria-label="Attach file"
              >
                <Plus className="h-4 w-4" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={onToggleWeb}
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all",
                  webEnabled
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                )}
              >
                <Globe className="h-3.5 w-3.5" strokeWidth={1.5} />
                Web
              </button>
            </div>
            <button
              type="button"
              onClick={onSend}
              disabled={!value.trim()}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-md shadow-primary/30 transition-all duration-300 hover:scale-105 hover:bg-primary/90 disabled:scale-100 disabled:opacity-40 disabled:shadow-none"
              aria-label="Send message"
            >
              <ArrowUp className="h-4 w-4" strokeWidth={2} />
            </button>
          </div>
        </div>
        <p className="mt-2 text-center text-xs text-muted-foreground">
          ResearchMate can make mistakes. Check important sources.
        </p>
      </div>
    </div>
  );
}
