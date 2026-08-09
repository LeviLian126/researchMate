// Owns chat workspace state, API orchestration, and user-action handlers independently of presentation.
"use client";

import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  apiFetch,
  type AskResponse,
  type ConversationMessage,
  type ConversationSummary,
  describeApiError,
  type DocumentRecord,
  fileTypeFromName,
  idempotencyKey,
  mimeForFileType,
  type ProjectRecord,
  type QuizHistoryResponse,
  type QuizResponse,
  type QuizSet,
  uploadReservedContent,
} from "../lib/api";
import {
  clearCompletedIntent,
  type IntentKeyState,
  resolveIntentKey,
} from "../lib/idempotent-intent";

interface UseChatWorkspaceOptions {
  suppliedProjectId?: string;
  projectMode: boolean;
}

interface UploadUrlResponse {
  document_id: string;
  upload_url: string;
}

/** Creates a local message used until the server returns the canonical conversation state. */
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

/** Coordinates personal and project chat state while exposing presentation-ready actions. */
export function useChatWorkspace({ suppliedProjectId, projectMode }: UseChatWorkspaceOptions) {
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
  const askIntent = useRef<IntentKeyState | null>(null);
  const quizIntent = useRef<IntentKeyState | null>(null);
  const quizHistoryLoadedFor = useRef<string | null>(null);
  const askInFlight = useRef(false);
  const quizInFlight = useRef(false);
  const routeBase = projectMode && suppliedProjectId
    ? `/app/projects/${suppliedProjectId}/chat`
    : "/app";

  useEffect(() => {
    if (suppliedProjectId) return;
    let active = true;
    void apiFetch<ProjectRecord>("/chat/bootstrap", { method: "POST" })
      .then((project) => { if (active) setResolvedProject(project); })
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

    /** Loads the selected conversation without allowing stale route requests to win. */
    async function loadConversation() {
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
        if (!selectedId) return;
        const [history, attached] = await Promise.all([
          apiFetch<{ messages: ConversationMessage[] }>(`/conversations/${selectedId}/messages`),
          projectMode
            ? Promise.resolve([] as DocumentRecord[])
            : apiFetch<DocumentRecord[]>(`/conversations/${selectedId}/documents`),
        ]);
        if (generation !== loadGeneration.current) return;
        setMessages(history.messages);
        setDocuments(attached);
        if (!requestedId) router.replace(`${routeBase}?conversation=${selectedId}`);
      } catch (requestError) {
        if (generation === loadGeneration.current) setError(describeApiError(requestError));
      } finally {
        if (generation === loadGeneration.current) setHistoryLoading(false);
      }
    }
    void loadConversation();
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
    if (!projectMode || !projectId || !quizOpen) return;
    if (quizHistoryLoadedFor.current === projectId) return;
    quizHistoryLoadedFor.current = projectId;
    let active = true;

    /** Restores the latest persisted quiz without blocking the chat workspace. */
    async function loadQuizHistory() {
      try {
        const history = await apiFetch<QuizHistoryResponse>(`/projects/${projectId}/quiz`);
        if (active) setQuiz(history.quiz_sets[0] ?? null);
      } catch (requestError) {
        if (!active) return;
        quizHistoryLoadedFor.current = null;
        setError(describeApiError(requestError));
      }
    }
    void loadQuizHistory();
    return () => { active = false; };
  }, [projectId, projectMode, quizOpen]);

  useEffect(() => {
    const processing = documents.some((document) =>
      ["uploaded", "parsing", "parsed", "indexing"].includes(document.status),
    );
    if (projectMode || !conversationId || !processing) return;
    const timer = window.setInterval(() => {
      void apiFetch<DocumentRecord[]>(`/conversations/${conversationId}/documents`)
        .then(setDocuments)
        .catch(() => undefined);
    }, 2_000);
    return () => window.clearInterval(timer);
  }, [conversationId, documents, projectMode]);

  const readyAttachments = useMemo(
    () => documents.filter((document) => document.status === "ready"),
    [documents],
  );

  /** Returns the current conversation or creates one for attachment uploads. */
  async function ensureConversation(): Promise<string> {
    if (conversationId) return conversationId;
    if (!projectId) throw new Error("Chat is still starting.");
    const created = await apiFetch<ConversationSummary>(`/projects/${projectId}/conversations`, {
      method: "POST",
      body: JSON.stringify({ title: message.trim().slice(0, 120) || "New chat" }),
    });
    setConversationId(created.id);
    router.replace(`${routeBase}?conversation=${created.id}`);
    window.dispatchEvent(new Event("researchmate:sidebar-refresh"));
    return created.id;
  }

  /** Validates, uploads, and completes selected source files in the active scope. */
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
          await uploadReservedContent(reservation.upload_url, file, mimeType);
        }
        await apiFetch(`/documents/${reservation.document_id}/complete`, {
          method: "POST",
          body: JSON.stringify({ extracted_text: localFallback ? await file.text() : null }),
        });
      }
      if (projectMode) {
        window.dispatchEvent(new Event("researchmate:sources-refresh"));
      } else if (activeConversationId) {
        setDocuments(await apiFetch(`/conversations/${activeConversationId}/documents`));
      }
    } catch (requestError) {
      setError(describeApiError(requestError));
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  /** Sends a question with optimistic feedback and restores the draft on failure. */
  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = message.trim();
    if (!prompt || !projectId || sending || historyLoading || askInFlight.current) return;
    askInFlight.current = true;
    const fingerprint = JSON.stringify({
      project_id: projectId,
      conversation_id: conversationId,
      message: prompt,
      web_enabled: webEnabled,
    });
    const intent = resolveIntentKey(askIntent.current, "ask", fingerprint, idempotencyKey);
    askIntent.current = intent;
    const optimisticUser = temporaryMessage(conversationId ?? "pending", "user", prompt);
    setMessages((current) => [...current, optimisticUser]);
    setMessage("");
    setError(null);
    setSending(true);
    try {
      const answer = await apiFetch<AskResponse>("/ask", {
        method: "POST",
        headers: { "Idempotency-Key": intent.key },
        body: JSON.stringify({
          project_id: projectId,
          conversation_id: conversationId,
          message: prompt,
          web_enabled: webEnabled,
        }),
      });
      setConversationId(answer.conversation_id);
      askIntent.current = clearCompletedIntent(askIntent.current, intent.key);
      setDegradedNotice(answer.rerank_degraded || answer.retrieval_degraded || answer.summary_degraded
        ? answer.fallback_reason || "One answer-processing stage used a safe fallback."
        : null);
      setMessages((current) => [
        ...current.map((item) => item.id === optimisticUser.id
          ? { ...item, conversation_id: answer.conversation_id }
          : item),
        { ...temporaryMessage(answer.conversation_id, "assistant", answer.answer), citations: answer.citations },
      ]);
      router.replace(`${routeBase}?conversation=${answer.conversation_id}`);
      window.dispatchEvent(new Event("researchmate:sidebar-refresh"));
    } catch (requestError) {
      setMessages((current) => current.filter((item) => item.id !== optimisticUser.id));
      setMessage(prompt);
      setError(describeApiError(requestError));
    } finally {
      askInFlight.current = false;
      setSending(false);
    }
  }

  /** Requests a project quiz using instructions that do not overstate source coverage. */
  async function generateQuiz(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !projectMode || quizLoading || quizInFlight.current) return;
    quizInFlight.current = true;
    const prompt = quizPrompt.trim() || "Generate a balanced quiz from available project resources.";
    const fingerprint = JSON.stringify({
      project_id: projectId,
      prompt,
      topic_query: null,
      resource_scope: "all_ready_documents",
      single_choice_count: 3,
      fill_blank_count: 2,
      subjective_count: 2,
    });
    const intent = resolveIntentKey(quizIntent.current, "quiz", fingerprint, idempotencyKey);
    quizIntent.current = intent;
    setQuizLoading(true);
    setError(null);
    try {
      const response = await apiFetch<QuizResponse>("/quiz", {
        method: "POST",
        headers: { "Idempotency-Key": intent.key },
        body: JSON.stringify({
          project_id: projectId,
          prompt,
          topic_query: null,
          resource_scope: "all_ready_documents",
          single_choice_count: 3,
          fill_blank_count: 2,
          subjective_count: 2,
        }),
      });
      setQuiz(response.quiz_set);
      quizIntent.current = clearCompletedIntent(quizIntent.current, intent.key);
    } catch (requestError) {
      setError(describeApiError(requestError));
    } finally {
      quizInFlight.current = false;
      setQuizLoading(false);
    }
  }

  /** Resets local state and navigates to a fresh project conversation. */
  function startNewProjectChat() {
    setConversationId(null);
    setMessages([]);
    setDocuments([]);
    setError(null);
    router.push(`${routeBase}?new=1`);
    window.dispatchEvent(new Event("researchmate:sidebar-refresh"));
  }

  return {
    projectId, messages, message, setMessage, webEnabled, setWebEnabled,
    historyLoading, sending, slowResponse, error, dismissError: () => setError(null),
    documents, readyAttachments, uploading, fileInput, threadEnd, degradedNotice,
    quizOpen, setQuizOpen, quizPrompt, setQuizPrompt, quiz, setQuiz,
    quizLoading, uploadFiles, submitQuestion, generateQuiz, startNewProjectChat,
  };
}
