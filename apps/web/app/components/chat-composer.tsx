// Owns chat draft controls, attachment selection, and submit accessibility semantics.
import type { ChangeEvent, FormEvent, RefObject } from "react";
import { SUPPORTED_FILE_ACCEPT, type DocumentRecord } from "../lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Paperclip, ArrowUp, Globe, Loader2 } from "lucide-react";

interface ChatComposerProps {
  documents: DocumentRecord[];
  projectMode: boolean;
  uploading: boolean;
  fileInput: RefObject<HTMLInputElement | null>;
  message: string;
  webEnabled: boolean;
  sending: boolean;
  historyLoading: boolean;
  hasReadyAttachments: boolean;
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onMessageChange: (message: string) => void;
  onWebEnabledChange: (enabled: boolean) => void;
}

/** Presents the form for attachments, message drafting, web scope, and submission. */
export function ChatComposer({
  documents,
  projectMode,
  uploading,
  fileInput,
  message,
  webEnabled,
  sending,
  historyLoading,
  hasReadyAttachments,
  onUpload,
  onSubmit,
  onMessageChange,
  onWebEnabledChange,
}: ChatComposerProps) {
  return (
    <div className="relative z-10 border-t border-white/30 bg-white/60 px-4 pb-3 pt-4 backdrop-blur-xl sm:px-6">
      {!!documents.length && !projectMode && (
        <div className="mx-auto mb-3 flex max-w-3xl flex-wrap gap-2">
          {documents.map((document) => (
            <span
              key={document.id}
              title={document.error_message ?? undefined}
              className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-white/50 px-3 py-1 text-xs text-muted-foreground backdrop-blur-sm"
            >
              <Paperclip className="h-3 w-3" strokeWidth={1.5} />
              {document.filename}
              <small className="font-medium text-muted-foreground/70">{document.status}</small>
            </span>
          ))}
        </div>
      )}
      <form
        onSubmit={onSubmit}
        className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-border/60 bg-card p-2 shadow-md transition-all duration-300 ease-out focus-within:scale-[1.01] focus-within:shadow-lg focus-within:shadow-primary/10"
      >
        <input
          ref={fileInput}
          className="sr-only"
          id="chat-files"
          type="file"
          accept={SUPPORTED_FILE_ACCEPT}
          multiple
          onChange={onUpload}
        />
        <label
          htmlFor="chat-files"
          aria-label="Add files"
          className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
          ) : (
            <Paperclip className="h-4 w-4" strokeWidth={1.5} />
          )}
        </label>
        <Textarea
          rows={1}
          maxLength={8000}
          value={message}
          onChange={(event) => onMessageChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
          placeholder={hasReadyAttachments ? "Ask about your files" : "Message ResearchMate"}
          aria-label="Message"
          className="min-h-[36px] resize-none border-0 bg-transparent px-1 py-1.5 text-sm shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
        />
        <label
          className={cn(
            "flex cursor-pointer items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all",
            webEnabled
              ? "bg-accent text-accent-foreground"
              : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
          )}
        >
          <input
            type="checkbox"
            checked={webEnabled}
            onChange={(event) => onWebEnabledChange(event.target.checked)}
            className="sr-only"
          />
          <Globe className="h-3.5 w-3.5" strokeWidth={1.5} />
          Web
        </label>
        <Button
          type="submit"
          size="icon"
          disabled={!message.trim() || sending || historyLoading}
          aria-label="Send message"
          className="h-9 w-9 shrink-0 rounded-full bg-primary text-primary-foreground shadow-md shadow-primary/30 transition-all hover:scale-105"
        >
          <ArrowUp strokeWidth={1.5} />
        </Button>
      </form>
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-muted-foreground">
        ResearchMate can make mistakes. Check important sources.
      </p>
    </div>
  );
}
