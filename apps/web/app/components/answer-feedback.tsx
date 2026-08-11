// Collects one accessible rating and optional Bad Case reason for a persisted answer.
"use client";

import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import type { FeedbackCategory, FeedbackRating } from "../lib/api";
import { Button } from "@/components/ui/button";

const CATEGORIES: Array<{ value: FeedbackCategory; label: string }> = [
  { value: "incorrect_answer", label: "Incorrect answer" },
  { value: "incorrect_citation", label: "Incorrect citation" },
  { value: "missing_context", label: "Missing context" },
  { value: "irrelevant", label: "Not relevant" },
  { value: "unsafe", label: "Unsafe content" },
  { value: "other", label: "Other" },
];

interface AnswerFeedbackProps {
  currentRating?: FeedbackRating | null;
  onSubmit: (
    rating: FeedbackRating,
    category: FeedbackCategory | null,
    comment: string | null,
  ) => Promise<void>;
}

/** Keeps feedback lightweight while preserving an explicit recovery path on failure. */
export function AnswerFeedback({ currentRating, onSubmit }: AnswerFeedbackProps) {
  const [expanded, setExpanded] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory>("incorrect_answer");
  const [comment, setComment] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Submits a rating once and leaves the controls available for correction. */
  async function submit(
    rating: FeedbackRating,
    selectedCategory: FeedbackCategory | null,
    detail: string | null,
  ) {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await onSubmit(rating, selectedCategory, detail);
      setExpanded(false);
    } catch {
      setError("Feedback was not saved. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mt-3 space-y-3" aria-label="Rate this answer">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">
          {currentRating ? "Feedback saved" : "Was this answer useful?"}
        </span>
        <button
          type="button"
          aria-label="Mark answer helpful"
          aria-pressed={currentRating === "helpful"}
          disabled={pending}
          onClick={() => void submit("helpful", null, null)}
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-border/60 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50 aria-pressed:border-primary aria-pressed:bg-primary/10 aria-pressed:text-primary"
        >
          <ThumbsUp className="size-4" strokeWidth={1.5} />
        </button>
        <button
          type="button"
          aria-label="Mark answer not helpful"
          aria-pressed={currentRating === "not_helpful"}
          aria-expanded={expanded}
          disabled={pending}
          onClick={() => setExpanded((current) => !current)}
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-border/60 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50 aria-pressed:border-destructive aria-pressed:bg-destructive/10 aria-pressed:text-destructive"
        >
          <ThumbsDown className="size-4" strokeWidth={1.5} />
        </button>
      </div>

      {expanded && (
        <form
          className="max-w-xl space-y-3 rounded-xl border border-border/60 bg-secondary/20 p-3"
          onSubmit={(event) => {
            event.preventDefault();
            void submit("not_helpful", category, comment.trim() || null);
          }}
        >
          <label className="block space-y-1.5 text-sm">
            <span className="font-medium text-foreground">What should improve?</span>
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value as FeedbackCategory)}
              className="min-h-11 w-full rounded-lg border border-border bg-background px-3"
            >
              {CATEGORIES.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="font-medium text-foreground">Optional detail</span>
            <textarea
              value={comment}
              maxLength={1000}
              rows={3}
              onChange={(event) => setComment(event.target.value)}
              className="w-full resize-y rounded-lg border border-border bg-background px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              placeholder="Describe the missing fact or citation. Do not include secrets."
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm" disabled={pending} className="min-h-11">
              {pending ? "Saving…" : "Send feedback"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setExpanded(false)}
              className="min-h-11"
            >
              Cancel
            </Button>
          </div>
        </form>
      )}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    </div>
  );
}
