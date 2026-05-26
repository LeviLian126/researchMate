export type SourceMode = "auto" | "local_only" | "web_only" | "hybrid";

export interface ProjectRecord {
  id: string;
  user_id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentRecord {
  id: string;
  user_id: string;
  project_id: string;
  filename: string;
  file_type: "pdf" | "docx" | "pptx" | string;
  mime_type: string;
  size_bytes: number;
  status: string;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  id: string;
  source_type: "local_doc" | "web_page";
  document_id?: string | null;
  chunk_id?: string | null;
  page_no?: number | null;
  slide_no?: number | null;
  url?: string | null;
  quote: string;
  claim_id?: string | null;
}

export interface AskResponse {
  run_id: string;
  answer: string;
  mode: SourceMode;
  sources: { local_chunks: number; web_pages: number };
  citations: Citation[];
  trace_id: string;
  validation_status: "passed" | "failed" | "retrying";
}

export interface QuizQuestion {
  id: string;
  type: "single_choice" | "short_answer";
  question: string;
  options?: string[] | null;
  answer: string;
  explanation: string;
  difficulty: "easy" | "medium" | "hard";
  source_citations: Citation[];
}

export interface QuizSet {
  id: string;
  mode: SourceMode;
  sources: { local_chunks: number; web_pages: number };
  questions: QuizQuestion[];
}

export interface DeveloperTrace {
  trace_id: string;
  user_id: string;
  project_id: string;
  run_id: string;
  execution_plan: Record<string, unknown>;
  router_reason: string;
  retrieved_chunks: Array<Record<string, unknown>>;
  tool_calls: Array<Record<string, unknown>>;
  validation_result: Record<string, unknown>;
  created_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function getDevToken(): string {
  if (typeof window === "undefined") {
    return "dev";
  }
  return window.localStorage.getItem("researchmate_token") || "dev";
}

export function setDevToken(token: string): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem("researchmate_token", token || "dev");
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getDevToken()}`,
      ...(init.headers || {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body?.error?.message || body?.detail || `Request failed with ${response.status}`;
    throw new Error(message);
  }
  return body as T;
}

export function fileTypeFromName(filename: string): "pdf" | "docx" | "pptx" {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".docx")) {
    return "docx";
  }
  if (lower.endsWith(".pptx")) {
    return "pptx";
  }
  return "pdf";
}

export function mimeForFileType(fileType: "pdf" | "docx" | "pptx"): string {
  if (fileType === "docx") {
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  }
  if (fileType === "pptx") {
    return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
  }
  return "application/pdf";
}
