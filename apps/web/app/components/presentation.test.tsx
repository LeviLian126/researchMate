// Exercises the visible chat and quiz states included in frontend coverage.
import { createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { ConversationMessage, DocumentRecord, QuizSet } from "../lib/api";
import { ChatComposer } from "./chat-composer";
import { ConversationThread } from "./conversation-thread";
import { ProjectQuizDrawer } from "./project-quiz-drawer";
import { StateNotice } from "./state-notice";

const assistantMessage: ConversationMessage = {
  id: "message-1",
  conversation_id: "conversation-1",
  role: "assistant",
  content: "The source supports the claim.",
  ask_run_id: "run-1",
  citations: [{
    id: "citation-1",
    source_type: "web_page",
    url: "https://example.com/source",
    quote: "Supporting evidence",
    page_no: null,
    document_id: null,
    chunk_id: null,
  }],
  created_at: "2026-08-04T00:00:00Z",
};

describe("chat presentation states", () => {
  it("renders empty, loading, answer, fallback, and error states", () => {
    const markup = renderToStaticMarkup(
      <ConversationThread
        messages={[assistantMessage]}
        historyLoading
        sending
        slowResponse
        error={{ title: "Request failed", detail: "Try again.", kind: "error" }}
        degradedNotice="semantic reranking was unavailable"
        projectMode
        projectName="Climate review"
        threadEnd={createRef<HTMLDivElement>()}
        onDismissError={vi.fn()}
        onSelectPrompt={vi.fn()}
        onSubmitFeedback={vi.fn()}
      />,
    );

    expect(markup).toContain("Loading conversation");
    expect(markup).toContain("https://example.com/source");
    expect(markup).toContain("Still working");
    expect(markup).toContain("Request failed");
    expect(markup).toContain("semantic reranking was unavailable");
    expect(markup).toContain("Was this answer useful?");

    const emptyMarkup = renderToStaticMarkup(
      <ConversationThread
        messages={[]}
        historyLoading={false}
        sending={false}
        slowResponse={false}
        error={null}
        degradedNotice={null}
        projectMode={false}
        threadEnd={createRef<HTMLDivElement>()}
        onDismissError={vi.fn()}
        onSelectPrompt={vi.fn()}
        onSubmitFeedback={vi.fn()}
      />,
    );
    expect(emptyMarkup).toContain("What can I help with?");
    expect(emptyMarkup).toContain("What assumptions should I verify?");
  });

  it("renders composer attachments and truthful source scope", () => {
    const document = {
      id: "document-1",
      filename: "paper.pdf",
      status: "ready",
      error_message: null,
    } as DocumentRecord;
    const markup = renderToStaticMarkup(
      <ChatComposer
        documents={[document]}
        projectMode={false}
        uploading={false}
        fileInput={createRef<HTMLInputElement>()}
        message="What is the conclusion?"
        webEnabled
        sending={false}
        historyLoading={false}
        hasReadyAttachments
        onUpload={vi.fn()}
        onSubmit={vi.fn()}
        onMessageChange={vi.fn()}
        onWebEnabledChange={vi.fn()}
      />,
    );
    expect(markup).toContain("paper.pdf");
    expect(markup).toContain("Ask about your files");
    expect(markup).toContain("composer-web is-active");
  });
});

describe("quiz and notice presentation", () => {
  it("renders both quiz generation and persisted question review", () => {
    const emptyMarkup = renderToStaticMarkup(
      <ProjectQuizDrawer
        prompt="Focus on methods"
        quiz={null}
        loading
        onPromptChange={vi.fn()}
        onSubmit={vi.fn()}
        onClose={vi.fn()}
        onReset={vi.fn()}
      />,
    );
    expect(emptyMarkup).toContain("Uses available indexed project resources");
    expect(emptyMarkup).toContain("Generating…");

    const quiz = {
      id: "quiz-1",
      questions: [{
        id: "question-1",
        question: "Which method was used?",
        options: ["A", "B"],
        answer: "A",
        explanation: "The cited method section says so.",
      }],
    } as QuizSet;
    const quizMarkup = renderToStaticMarkup(
      <ProjectQuizDrawer
        prompt=""
        quiz={quiz}
        loading={false}
        onPromptChange={vi.fn()}
        onSubmit={vi.fn()}
        onClose={vi.fn()}
        onReset={vi.fn()}
      />,
    );
    expect(quizMarkup).toContain("Which method was used?");
    expect(quizMarkup).toContain("Generate another");
  });

  it("uses an alert role only for actionable failures", () => {
    expect(renderToStaticMarkup(
      <StateNotice state={{ title: "Offline", detail: "Retry later", kind: "provider" }} />,
    )).toContain('role="alert"');
    expect(renderToStaticMarkup(
      <StateNotice state={{ title: "Saved", detail: "Ready" }} />,
    )).toContain('role="status"');
  });
});
