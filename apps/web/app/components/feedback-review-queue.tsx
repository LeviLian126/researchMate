// Presents developer-only Bad Case review and explicit evidence promotion controls.
"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  apiFetch,
  type AnswerFeedbackRecord,
  describeApiError,
  type FeedbackPromotionResult,
} from "../lib/api";
import { Button } from "@/components/ui/button";

interface FeedbackReviewQueueProps {
  projectId: string;
  onDatasetCreated: (result: FeedbackPromotionResult) => void;
}

interface FeedbackReviewItemProps {
  record: AnswerFeedbackRecord;
  busy: boolean;
  onPromote: (record: AnswerFeedbackRecord, chunkIds: string[]) => Promise<void>;
}

function FeedbackReviewItem({ record, busy, onPromote }: FeedbackReviewItemProps) {
  const replayableEvidence = record.retrieved_evidence.filter(
    (evidence) => evidence.source_type === "local_doc",
  );
  const cited = new Set(record.citation_chunk_ids);
  const [selected, setSelected] = useState<string[]>(
    replayableEvidence.map((evidence) => evidence.chunk_id).filter((chunkId) => cited.has(chunkId)),
  );

  function toggle(chunkId: string) {
    setSelected((current) => current.includes(chunkId)
      ? current.filter((value) => value !== chunkId)
      : [...current, chunkId]);
  }

  return (
    <article className="space-y-3 border-t border-border/60 pt-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground">{record.question}</p>
          <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{record.answer}</p>
        </div>
        <span className="rounded-md border border-border/60 px-2 py-1 text-sm text-muted-foreground">
          {record.category?.replaceAll("_", " ") ?? record.rating.replaceAll("_", " ")}
        </span>
      </div>
      {record.comment && <p className="text-sm text-muted-foreground">Reviewer note: {record.comment}</p>}
      {record.status === "promoted" ? (
        <p className="text-sm font-medium text-emerald-700">Included in a frozen regression set.</p>
      ) : replayableEvidence.length ? (
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-foreground">
            Select evidence that should be retrieved for this question
          </legend>
          {replayableEvidence.map((evidence) => (
            <label
              key={evidence.chunk_id}
              className="flex cursor-pointer items-start gap-3 rounded-lg border border-border/60 p-3 text-sm"
            >
              <input
                type="checkbox"
                checked={selected.includes(evidence.chunk_id)}
                onChange={() => toggle(evidence.chunk_id)}
                className="mt-1 size-4 accent-primary"
              />
              <span className="min-w-0">
                <span className="block font-medium text-foreground">
                  {evidence.source_title || "Project source"}
                  {evidence.page_no ? ` · page ${evidence.page_no}` : ""}
                  {cited.has(evidence.chunk_id) ? " · cited" : ""}
                </span>
                <span className="mt-1 block break-words text-muted-foreground">
                  {evidence.excerpt || evidence.chunk_id}
                </span>
              </span>
            </label>
          ))}
          <Button
            type="button"
            size="sm"
            disabled={busy || selected.length === 0}
            onClick={() => void onPromote(record, selected)}
            className="min-h-11"
          >
            {busy ? "Creating dataset…" : "Promote selected evidence"}
          </Button>
        </fieldset>
      ) : (
        <p className="text-sm text-muted-foreground">
          This answer has no local retrieved evidence and cannot become a retrieval benchmark case.
        </p>
      )}
    </article>
  );
}

/** Owns the bounded review queue, promotion lifecycle, and recoverable error state. */
export function FeedbackReviewQueue({ projectId, onDatasetCreated }: FeedbackReviewQueueProps) {
  const [records, setRecords] = useState<AnswerFeedbackRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<{ items: AnswerFeedbackRecord[] }>(
        `/projects/${projectId}/answer-feedback?rating=not_helpful`,
      );
      setRecords(result.items);
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { void load(); }, [load]);

  async function promote(record: AnswerFeedbackRecord, chunkIds: string[]) {
    setBusyId(record.feedback_id);
    setError(null);
    try {
      const result = await apiFetch<FeedbackPromotionResult>(
        `/answer-feedback/${record.feedback_id}/promote`,
        { method: "POST", body: JSON.stringify({ expected_chunk_ids: chunkIds }) },
      );
      setRecords((current) => current.map((item) => (
        item.feedback_id === record.feedback_id
          ? { ...item, status: "promoted", promoted_case_id: result.case_id }
          : item
      )));
      onDatasetCreated(result);
    } catch (requestError) {
      setError(describeApiError(requestError).detail);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="space-y-4" aria-labelledby="feedback-review-heading">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 id="feedback-review-heading" className="text-lg font-semibold text-foreground">
            Bad Case review
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Review negative feedback, choose expected evidence, then create a frozen dataset version.
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void load()} disabled={loading} className="min-h-11">
          <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} strokeWidth={1.5} />
          Refresh
        </Button>
      </div>
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      {loading ? (
        <p className="text-sm text-muted-foreground" role="status">Loading feedback…</p>
      ) : records.length ? (
        <div className="space-y-4">
          {records.map((record) => (
            <FeedbackReviewItem
              key={record.feedback_id}
              record={record}
              busy={busyId === record.feedback_id}
              onPromote={promote}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No negative feedback is waiting for review in this project.
        </p>
      )}
    </section>
  );
}
