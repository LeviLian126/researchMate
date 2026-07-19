import { getSupabaseSession, isLocalDevelopment } from "./supabase";
import { demoFetch, demoRunEvents, isPublicDemo } from "./demo";

export type SourceMode = "auto" | "local_only" | "web_only" | "hybrid";
export type RunStatus = "pending" | "running" | "waiting_human" | "succeeded" | "failed" | "cancelled";

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

export interface ResearchRunAccepted {
  run_id: string;
  status: "pending";
  status_url: string;
  events_url: string;
  created_at: string;
}

export interface WorkflowRun {
  run_id: string;
  project_id: string;
  pipeline_version_id: string;
  kind: "ask" | "evidence_review" | "report_refresh";
  status: RunStatus;
  progress: number;
  current_node?: string | null;
  review_required: boolean;
  output?: Record<string, unknown> | null;
  error_code?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface RunEvent {
  event_id: number;
  sequence: number;
  node_key: string;
  event_type: string;
  attempt: number;
  status: string;
  safe_payload: Record<string, unknown>;
  latency_ms?: number | null;
  created_at: string;
}

export interface ClaimSummary {
  claim_id: string;
  text: string;
  stance: "supports" | "opposes" | "neutral";
  confidence: number;
  review_status: "pending" | "accepted" | "edited" | "rejected" | "invalidated";
  evidence_count: number;
  support_count: number;
  contradiction_count: number;
  duplicate_count: number;
  source_version: number;
}

export interface ClaimRelationSummary {
  source_claim_id: string;
  target_claim_id: string;
  relation: "supports" | "contradicts" | "duplicates";
  confidence: number;
  rationale_summary?: string | null;
  source_text: string;
  target_text: string;
}

export interface ReportSummary {
  report_id: string;
  source_run_id: string;
  title: string;
  status: "draft" | "review" | "published" | "invalidated";
  revision: number;
  validation_status: "pending" | "passed" | "failed" | "retrying";
  affected_section_count: number;
  generated_at?: string | null;
}

export interface ReportSectionRecord {
  section_id: string;
  section_key: string;
  position: number;
  heading: string;
  body_markdown: string;
  evidence_snapshot: Record<string, unknown>;
  validation_status: "pending" | "passed" | "failed" | "retrying";
}

export interface ReportDetail extends ReportSummary {
  sections: ReportSectionRecord[];
}

export interface PipelineVersionSummary {
  pipeline_version_id: string;
  name: string;
  version: number;
  configuration: Record<string, unknown>;
  code_sha: string;
  accepted_at?: string | null;
}

export interface EvaluationDatasetSummary {
  dataset_id: string;
  project_id?: string | null;
  name: string;
  version: number;
  description?: string | null;
  case_count: number;
}

export interface EvaluationRunAccepted {
  evaluation_run_id: string;
  case_count: number;
  status_url: string;
  estimated_budget_boundary?: string | number | null;
}

export interface EvaluationRun {
  evaluation_run_id: string;
  dataset_id: string;
  pipeline_version_id: string;
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  summary?: Record<string, unknown> | null;
  scores: Array<Record<string, unknown>>;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ReliabilityMetrics {
  window_hours: number;
  run_count: number;
  success_rate: number;
  error_rate: number;
  retry_count: number;
  p50_latency_ms?: number | null;
  p95_latency_ms?: number | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: string | number;
  sample_trace_ids: string[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function getDevToken(): string {
  if (isPublicDemo()) return "public-demo";
  if (!isLocalDevelopment()) throw new ApiError("A Supabase session is required outside local development.", 401, "AUTH_REQUIRED");
  if (typeof window === "undefined") return "dev";
  return window.localStorage.getItem("researchmate_token") || "dev";
}

export function setDevToken(token: string): void {
  if (!isLocalDevelopment()) return;
  if (typeof window !== "undefined") window.localStorage.setItem("researchmate_token", token || "dev");
}

async function getAccessToken(): Promise<string> {
  if (isLocalDevelopment()) return getDevToken();
  let session;
  try {
    session = await getSupabaseSession();
  } catch {
    throw new ApiError("Supabase could not refresh the browser session.", 503, "AUTH_PROVIDER_UNAVAILABLE");
  }
  if (!session?.access_token) throw new ApiError("Sign in before accessing this workspace.", 401, "AUTH_REQUIRED");
  return session.access_token;
}

function toApiError(response: Response, body: Record<string, unknown>): ApiError {
  const detail = body.error && typeof body.error === "object" ? body.error as Record<string, unknown> : body;
  const code = typeof detail.code === "string" ? detail.code : `HTTP_${response.status}`;
  const message = typeof detail.message === "string"
    ? detail.message
    : typeof body.detail === "string" ? body.detail : `Request failed with ${response.status}`;
  return new ApiError(message, response.status, code, typeof detail.request_id === "string" ? detail.request_id : undefined);
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (isPublicDemo()) return demoFetch<T>(path, init);
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  headers.set("Authorization", `Bearer ${await getAccessToken()}`);
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  const body = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) throw toApiError(response, body);
  return body as T;
}

export async function streamRunEvents(
  runId: string,
  afterSequence: number,
  onEvent: (event: RunEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  if (isPublicDemo()) {
    await demoRunEvents(onEvent, signal);
    return;
  }
  const response = await fetch(`${API_BASE}/runs/${runId}/events?after_sequence=${afterSequence}`, {
    headers: { Authorization: `Bearer ${await getAccessToken()}`, Accept: "text/event-stream" },
    signal,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as Record<string, unknown>;
    throw toApiError(response, body);
  }
  if (!response.body) throw new ApiError("The event stream is unavailable.", 503, "EVENT_STREAM_UNAVAILABLE");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLine = frame.split("\n").find((line) => line.startsWith("data: "));
      if (!dataLine) continue;
      try {
        onEvent(JSON.parse(dataLine.slice(6)) as RunEvent);
      } catch {
        // Ignore a malformed provider frame; the canonical run status remains recoverable via polling.
      }
    }
  }
}

export function idempotencyKey(prefix: string): string {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${random}`;
}

export function describeApiError(error: unknown): { title: string; detail: string; kind: string } {
  if (!(error instanceof ApiError)) {
    return { title: "Request could not be completed", detail: error instanceof Error ? error.message : "Unknown client error.", kind: "error" };
  }
  if (error.status === 401) return { title: "Authentication required", detail: isLocalDevelopment() ? "Set a valid local development identity and retry." : "Sign in again to restore a verified Supabase session, then retry.", kind: "auth" };
  if (error.status === 403) return { title: "Developer access required", detail: "This lab is restricted to a developer or admin identity.", kind: "permission" };
  if (error.status === 409) return { title: "State changed", detail: `${error.message} Refresh the canonical run state before retrying.`, kind: "conflict" };
  if (error.status === 429) return { title: "Usage limit reached", detail: "The demo budget refused this request. Retry after the limit window resets.", kind: "limit" };
  if (error.status >= 500) return { title: "Provider or service unavailable", detail: "The request is safe to retry. Existing run data has not been discarded.", kind: "provider" };
  return { title: error.code.replaceAll("_", " "), detail: error.message, kind: "validation" };
}

export function fileTypeFromName(filename: string): "pdf" | "docx" | "pptx" {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".docx")) return "docx";
  if (lower.endsWith(".pptx")) return "pptx";
  return "pdf";
}

export function mimeForFileType(fileType: "pdf" | "docx" | "pptx"): string {
  if (fileType === "docx") return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  if (fileType === "pptx") return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
  return "application/pdf";
}
