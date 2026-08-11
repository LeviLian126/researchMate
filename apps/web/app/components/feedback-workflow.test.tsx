// Exercises answer rating and developer Bad Case promotion through visible controls.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiFetchMock = vi.fn();

vi.mock("../lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  describeApiError: (error: unknown) => ({
    title: "Request failed",
    detail: error instanceof Error ? error.message : "Unknown error",
    kind: "error",
  }),
}));

import { AnswerFeedback } from "./answer-feedback";
import { FeedbackReviewQueue } from "./feedback-review-queue";

async function flushAsyncQueue(times = 6): Promise<void> {
  for (let step = 0; step < times; step += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => { await Promise.resolve(); });
  }
}

describe("answer feedback controls", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    apiFetchMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  it("submits a helpful rating without manufacturing a Bad Case reason", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    await act(async () => root.render(
      <AnswerFeedback currentRating={null} onSubmit={onSubmit} />,
    ));

    const helpful = container.querySelector<HTMLButtonElement>(
      'button[aria-label="Mark answer helpful"]',
    );
    await act(async () => helpful?.click());

    expect(onSubmit).toHaveBeenCalledWith("helpful", null, null);
    expect(helpful?.getAttribute("aria-pressed")).toBe("false");
  });

  it("collects an explicit negative category and exposes a recoverable error", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("offline"));
    await act(async () => root.render(
      <AnswerFeedback currentRating={null} onSubmit={onSubmit} />,
    ));
    act(() => container.querySelector<HTMLButtonElement>(
      'button[aria-label="Mark answer not helpful"]',
    )?.click());
    const select = container.querySelector<HTMLSelectElement>("select");
    const comment = container.querySelector<HTMLTextAreaElement>("textarea");
    act(() => {
      if (select) {
        select.value = "missing_context";
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (comment) {
        Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")
          ?.set?.call(comment, "Missing the methods section");
        comment.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
    await act(async () => container.querySelector<HTMLButtonElement>('button[type="submit"]')?.click());

    expect(onSubmit).toHaveBeenCalledWith(
      "not_helpful",
      "missing_context",
      "Missing the methods section",
    );
    expect(container.querySelector('[role="alert"]')?.textContent)
      .toContain("Feedback was not saved");
  });
});

describe("developer feedback review", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    apiFetchMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  it("loads negative feedback and promotes only the selected retrieved evidence", async () => {
    apiFetchMock.mockImplementation(async (path: string) => {
      if (path.includes("/projects/project-1/answer-feedback")) {
        return {
          items: [{
            feedback_id: "feedback-1",
            ask_run_id: "run-1",
            project_id: "project-1",
            conversation_id: "conversation-1",
            rating: "not_helpful",
            category: "incorrect_citation",
            comment: "Wrong page",
            question: "Which method was used?",
            answer: "Method A",
            citation_chunk_ids: ["chunk-1"],
            retrieved_chunk_ids: ["chunk-1", "chunk-2"],
            retrieved_evidence: [
              { chunk_id: "chunk-1", source_type: "local_doc", source_title: "Paper", page_no: 3, excerpt: "Method A" },
              { chunk_id: "chunk-2", source_type: "local_doc", source_title: "Appendix", page_no: 8, excerpt: "Method B" },
            ],
            status: "new",
            promoted_case_id: null,
            created_at: "2026-08-11T00:00:00Z",
            updated_at: "2026-08-11T00:00:00Z",
          }],
        };
      }
      return { dataset_id: "dataset-1", dataset_version: 1, dataset_status: "frozen", case_id: "case-1" };
    });
    const onDatasetCreated = vi.fn();
    await act(async () => root.render(
      <FeedbackReviewQueue projectId="project-1" onDatasetCreated={onDatasetCreated} />,
    ));
    await flushAsyncQueue();

    expect(container.textContent).toContain("Which method was used?");
    expect(container.textContent).toContain("Paper · page 3 · cited");
    const checkboxes = container.querySelectorAll<HTMLInputElement>('input[type="checkbox"]');
    act(() => checkboxes[0]?.click());
    let promote = [...container.querySelectorAll("button")]
      .find((button) => button.textContent?.includes("Promote selected evidence"));
    expect(promote?.hasAttribute("disabled")).toBe(true);
    act(() => checkboxes[1]?.click());
    promote = [...container.querySelectorAll("button")]
      .find((button) => button.textContent?.includes("Promote selected evidence"));
    await act(async () => promote?.click());
    await flushAsyncQueue();

    expect(apiFetchMock).toHaveBeenLastCalledWith(
      "/answer-feedback/feedback-1/promote",
      { method: "POST", body: JSON.stringify({ expected_chunk_ids: ["chunk-2"] }) },
    );
    expect(onDatasetCreated).toHaveBeenCalledWith(expect.objectContaining({ dataset_version: 1 }));
    expect(container.textContent).toContain("Included in a frozen regression set");
  });
});
