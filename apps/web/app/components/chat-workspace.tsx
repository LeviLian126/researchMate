"use client";

import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  apiFetch,
  AskResponse,
  ConversationMessage,
  ConversationSummary,
  describeApiError,
  DocumentRecord,
  fileTypeFromName,
  mimeForFileType,
  ProjectRecord,
  QuizSet,
} from "../lib/api";
import { StateNotice } from "./state-notice";

interface ChatWorkspaceProps {
  projectId?: string;
  projectName?: string;
  projectMode?: boolean;
}

interface UploadUrlResponse {
  document_id: string;
  upload_url: string;
}

const EMPTY_PROMPTS = [
  "Summarize the material and identify its strongest claim.",
  "What assumptions should I verify?",
  "Turn these ideas into a clear research plan.",
];

function temporaryMessage(
  conversationId: string,
  role: "user" | "assistant",
  content: string,
): ConversationMessage {
  return {
    id: `temp-${role}-${Date.now()}-${Math.random()}`,
    conversation_id: conversationId,
    role,
    content,
    citations: [],
    created_at: new Date().toISOString(),
  };
}

/** Provides one persistent chat surface for personal conversations and project work. */
export function ChatWorkspace({
  projectId: suppliedProjectId,
  projectName,
  projectMode = false,
}: ChatWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [resolvedProject, setResolvedProject] = useState<ProjectRecord | null>(null);
  const projectId = suppliedProjectId ?? resolvedProject?.id ?? null;
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [message, setMessage] = useState("");
  const [webEnabled, setWebEnabled] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [slowResponse, setSlowResponse] = useState(false);
  const [error, setError] = useState<ReturnType<typeof describeApiError> | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [uploading, setUploading] = useState(false);
  const [quizOpen, setQuizOpen] = useState(searchParams.get("quiz") === "1");
  const [quizPrompt, setQuizPrompt] = useState("");
  const [quiz, setQuiz] = useState<QuizSet | null>(null);
  const [quizLoading, setQuizLoading] = useState(false);
  const [degradedNotice, setDegradedNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const threadEnd = useRef<HTMLDivElement>(null);
  const loadGeneration = useRef(0);

  const routeBase = projectMode && suppliedProjectId
    ? `/app/projects/${suppliedProjectId}/chat`
    : "/app";

  useEffect(() => {
    if (suppliedProjectId) return;
    let active = true;
    void apiFetch<ProjectRecord>("/chat/bootstrap", { method: "POST" })
      .then((project) => {
        if (active) setResolvedProject(project);
      })
      .catch((requestError) => {
        if (active) {
          setError(describeApiError(requestError));
          setHistoryLoading(false);
        }
      });
    return () => { active = false; };
  }, [suppliedProjectId]);

  useEffect(() => {
    if (!projectId) return;
    const generation = ++loadGeneration.current;
    const requestedId = searchParams.get("conversation");
    setError(null);
    setMessages([]);
    setDocuments([]);
    setHistoryLoading(true);

    async function load() {
      try {
        let selectedId = requestedId;
        if (!selectedId && searchParams.get("new") !== "1") {
          const body = await apiFetch<{ items: ConversationSummary[] }>(
            `/projects/${projectId}/conversations`,
          );
          selectedId = body.items[0]?.id ?? null;
        }
        if (generation !== loadGeneration.current) return;
        setConversationId(selectedId);
        if (!selectedId) {
          setHistoryLoading(false);
          return;
        }
        const [history, attached] = await Promise.all([
          apiFetch<{ messages: ConversationMessage[] }>(
            `/conversations/${selectedId}/messages`,
          ),
          projectMode
            ? Promise.resolve([] as DocumentRecord[])
            : apiFetch<DocumentRecord[]>(`/conversations/${selectedId}/documents`),
        ]);
        if (generation !== loadGeneration.current) return;
        setMessages(history.messages);
        setDocuments(attached);
        if (!requestedId) {
          router.replace(`${routeBase}?conversation=${selectedId}`);
        }
      } catch (requestError) {
        if (generation === loadGeneration.current) {
          setError(describeApiError(requestError));
        }
      } finally {
        if (generation === loadGeneration.current) setHistoryLoading(false);
      }
    }
    void load();
    return () => { loadGeneration.current += 1; };
  }, [projectId, projectMode, routeBase, router, searchParams]);

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ behavior: messages.length > 2 ? "smooth" : "auto" });
  }, [messages, sending]);

  useEffect(() => {
    if (!sending) {
      setSlowResponse(false);
      return;
    }
    const timer = window.setTimeout(() => setSlowResponse(true), 10_000);
    return () => window.clearTimeout(timer);
  }, [sending]);

  useEffect(() => {
    if (
      projectMode
      || !conversationId
      || !documents.some((document) =>
        ["uploaded", "parsing", "parsed", "indexing"].includes(document.status),
      )
    ) {
      return;
    }
    const timer = window.setInterval(() => {
      void apiFetch<DocumentRecord[]>(
        `/conversations/${conversationId}/documents`,
      ).then(setDocuments).catch(() => undefined);
    }, 2_000);
    return () => window.clearInterval(timer);
  }, [conversationId, documents, projectMode]);

  const readyAttachments = useMemo(
    () => documents.filter((document) => document.status === "ready"),
    [documents],
  );

  async function ensureConversation(): Promise<string> {
    if (conversationId) return conversationId;
    if (!projectId) throw new Error("Chat is still starting.");
    const created = await apiFetch<ConversationSummary>(
      `/projects/${projectId}/conversations`,
      {
        method: "POST",
        body: JSON.stringify({ title: message.trim().slice(0, 120) || "New chat" }),
      },
    );
    setConversationId(created.id);
    router.replace(`${routeBase}?conversation=${created.id}`);
    window.dispatchEvent(new Event("researchmate:sidebar-refresh"));
    return created.id;
  }

  async function uploadFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (!files.length || !projectId) return;
    setUploading(true);
    setError(null);
    try {
      const activeConversationId = projectMode ? null : await ensureConversation();
      for (const file of files) {
        if (!/\.(pdf|docx|pptx)$/i.test(file.name)) {
          throw new Error(`${file.name} is not a PDF, DOCX, or PPTX file.`);
        }
        const fileType = fileTypeFromName(file.name);
        const mimeType = mimeForFileType(fileType);
        const reservation = await apiFetch<UploadUrlResponse>("/documents/upload-url", {
          method: "POST",
          body: JSON.stringify({
            project_id: projectId,
            conversation_id: activeConversationId,
            filename: file.name,
            file_type: fileType,
            mime_type: mimeType,
            size_bytes: file.size,
          }),
        });
        const localFallback = reservation.upload_url.includes("/api/v1/dev/upload/");
        if (!localFallback) {
          const response = await fetch(reservation.upload_url, {
            method: "PUT",
            headers: { "Content-Type": mimeType },
            body: file,
          });
          if (!response.ok) throw new Error(`Upload failed for ${file.name}.`);
        }
        await apiFetch(`/documents/${reservation.document_id}/complete`, {
          method: "POST",
          body: JSON.stringify({
            extracted_text: localFallback ? await file.text() : null,
          }),
        });
      }
      if (projectMode) {
        window.dispatchEvent(new Event("researchmate:sources-refresh"));
      } else if (activeConversationId) {
        setDocuments(
          await apiFetch<DocumentRecord[]>(
            `/conversations/${activeConversationId}/documents`,
          ),
        );
      }
    } catch (requestError) {
      setError(describeApiError(requestError));
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = message.trim();
    if (!prompt || !projectId || sending || historyLoading) return;
    const optimisticConversation = conversationId ?? "pending";
    const optimisticUser = temporaryMessage(optimisticConversation, "user", prompt);
    setMessages((current) => [...current, optimisticUser]);
    setMessage("");
    setError(null);
    setSending(true);
    try {
      const answer = await apiFetch<AskResponse>("/ask", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          conversation_id: conversationId,
          message: prompt,
          web_enabled: webEnabled,
        }),
      });
      setConversationId(answer.conversation_id);
      setDegradedNotice(
        answer.rerank_degraded
          ? answer.fallback_reason || "Evidence ranking used the deterministic fallback."
          : null,
      );
      setMessages((current) => [
        ...current.map((item) =>
          item.id === optimisticUser.id
            ? { ...item, conversation_id: answer.conversation_id }
            : item,
        ),
        {
          ...temporaryMessage(answer.conversation_id, "assistant", answer.answer),
          citations: answer.citations,
        },
      ]);
      router.replace(`${routeBase}?conversation=${answer.conversation_id}`);
      window.dispatchEvent(new Event("researchmate:sidebar-refresh"));
    } catch (requestError) {
      setMessages((current) => current.filter((item) => item.id !== optimisticUser.id));
      setMessage(prompt);
      setError(describeApiError(requestError));
    } finally {
      setSending(false);
    }
  }

  async function generateQuiz(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !projectMode) return;
    setQuizLoading(true);
    setError(null);
    try {
      const response = await apiFetch<{ quiz_set: QuizSet }>("/quiz", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          prompt: quizPrompt.trim() || "Generate a balanced quiz from all project resources.",
          single_choice_count: 3,
          fill_blank_count: 2,
          subjective_count: 2,
        }),
      });
      setQuiz(response.quiz_set);
    } catch (requestError) {
      setError(describeApiError(requestError));
    } finally {
      setQuizLoading(false);
    }
  }

  function startNewProjectChat() {
    setConversationId(null);
    setMessages([]);
    setDocuments([]);
    setError(null);
    router.push(`${routeBase}?new=1`);
    window.dispatchEvent(new Event("researchmate:sidebar-refresh"));
  }

  return (
    <main className="conversation-shell">
      {projectMode && (
        <header className="conversation-topbar">
          <strong>{projectName ?? "Project"}</strong>
          <nav aria-label="Project tools">
            <button type="button" onClick={startNewProjectChat}>New chat</button>
            <button type="button" onClick={() => setQuizOpen((current) => !current)}>
              Quiz
            </button>
            <a href={`/app/projects/${projectId}/library`}>Sources</a>
          </nav>
        </header>
      )}

      <section className="conversation-thread" aria-live="polite">
        {!messages.length && !historyLoading && (
          <div className="conversation-empty">
            <h1>{projectMode ? `Chat in ${projectName ?? "this project"}` : "What can I help with?"}</h1>
            <div>
              {EMPTY_PROMPTS.map((prompt) => (
                <button key={prompt} type="button" onClick={() => setMessage(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
        {historyLoading && <div className="message-skeleton" role="status">Loading conversation</div>}
        {messages.map((item) => (
          <article
            className={`conversation-message conversation-message--${item.role}`}
            key={item.id}
          >
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
            action={<button type="button" onClick={() => setError(null)}>Dismiss</button>}
          />
        )}
        {degradedNotice && (
          <p className="conversation-degraded" role="status">
            Evidence ranking fallback: {degradedNotice}
          </p>
        )}
        <div ref={threadEnd} />
      </section>

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
        <form className="conversation-composer" onSubmit={submitQuestion}>
          <input
            ref={fileInput}
            className="sr-only"
            id="chat-files"
            type="file"
            accept=".pdf,.docx,.pptx"
            multiple
            onChange={uploadFiles}
          />
          <label htmlFor="chat-files" className="composer-icon-button" aria-label="Add files">
            {uploading ? "…" : "+"}
          </label>
          <textarea
            rows={1}
            maxLength={8000}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder={readyAttachments.length ? "Ask about your files" : "Message ResearchMate"}
            aria-label="Message"
          />
          <label className={`composer-web ${webEnabled ? "is-active" : ""}`}>
            <input
              type="checkbox"
              checked={webEnabled}
              onChange={(event) => setWebEnabled(event.target.checked)}
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
        <small className="composer-note">
          ResearchMate can make mistakes. Check important sources.
        </small>
      </div>

      {projectMode && quizOpen && (
        <aside className="quiz-drawer" aria-label="Project quiz">
          <div className="quiz-drawer__header">
            <div><strong>Project quiz</strong><small>Uses every ready project resource</small></div>
            <button type="button" onClick={() => setQuizOpen(false)} aria-label="Close quiz">×</button>
          </div>
          {!quiz ? (
            <form onSubmit={generateQuiz}>
              <textarea
                rows={3}
                value={quizPrompt}
                onChange={(event) => setQuizPrompt(event.target.value)}
                placeholder="Optional instructions, topics, or difficulty"
              />
              <p>Default: 3 multiple choice, 2 fill-in, and 2 subjective questions.</p>
              <button type="submit" disabled={quizLoading}>
                {quizLoading ? "Generating…" : "Generate quiz"}
              </button>
            </form>
          ) : (
            <div className="quiz-drawer__questions">
              {quiz.questions.map((question, index) => (
                <details key={question.id}>
                  <summary>{index + 1}. {question.question}</summary>
                  {question.options && <ol>{question.options.map((option) => <li key={option}>{option}</li>)}</ol>}
                  <p><strong>Answer:</strong> {question.answer}</p>
                  <small>{question.explanation}</small>
                </details>
              ))}
              <button type="button" onClick={() => setQuiz(null)}>Generate another</button>
            </div>
          )}
        </aside>
      )}
    </main>
  );
}
