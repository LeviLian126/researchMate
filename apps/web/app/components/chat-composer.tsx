// Owns chat draft controls, attachment selection, and submit accessibility semantics.
import type { ChangeEvent, FormEvent, RefObject } from "react";
import type { DocumentRecord } from "../lib/api";

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
    <div className="conversation-composer-wrap">
      {!!documents.length && !projectMode && (
        <div className="attachment-strip">
          {documents.map((document) => (
            <span key={document.id} title={document.error_message ?? undefined}>
              {document.filename}
              <small>{document.status}</small>
            </span>
          ))}
        </div>
      )}
      <form className="conversation-composer" onSubmit={onSubmit}>
        <input
          ref={fileInput}
          className="sr-only"
          id="chat-files"
          type="file"
          accept=".pdf,.docx,.pptx"
          multiple
          onChange={onUpload}
        />
        <label htmlFor="chat-files" className="composer-icon-button" aria-label="Add files">
          {uploading ? "…" : "+"}
        </label>
        <textarea
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
        />
        <label className={`composer-web ${webEnabled ? "is-active" : ""}`}>
          <input
            type="checkbox"
            checked={webEnabled}
            onChange={(event) => onWebEnabledChange(event.target.checked)}
          />
          Web
        </label>
        <button
          className="composer-send"
          type="submit"
          disabled={!message.trim() || sending || historyLoading}
          aria-label="Send message"
        >
          ↑
        </button>
      </form>
      <small className="composer-note">ResearchMate can make mistakes. Check important sources.</small>
    </div>
  );
}
