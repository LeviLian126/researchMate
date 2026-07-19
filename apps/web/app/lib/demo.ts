const DEMO_PROJECT_ID = "11111111-1111-4111-8111-111111111111";
const DEMO_DOCUMENT_ID = "22222222-2222-4222-8222-222222222222";
const DEMO_PIPELINE_ID = "33333333-3333-4333-8333-333333333333";
const DEMO_REPORT_ID = "55555555-5555-4555-8555-555555555555";
const DEMO_DATASET_ID = "66666666-6666-4666-8666-666666666666";

type Json = Record<string, unknown>;

interface DemoRunEvent {
  event_id: number;
  sequence: number;
  node_key: string;
  event_type: string;
  attempt: number;
  status: string;
  safe_payload: Record<string, unknown>;
  latency_ms?: number;
  created_at: string;
}

const timestamp = "2026-07-19T08:00:00.000Z";
let projectSequence = 1;
let runSequence = 1;
let evaluationSequence = 1;
let documentSequence = 1;

const projects: Json[] = [{
  id: DEMO_PROJECT_ID,
  user_id: "public-demo",
  name: "Evidence review walkthrough",
  status: "active",
  created_at: timestamp,
  updated_at: timestamp,
}];

const documents: Json[] = [{
  id: DEMO_DOCUMENT_ID,
  user_id: "public-demo",
  project_id: DEMO_PROJECT_ID,
  filename: "retrieval-reliability-brief.pdf",
  file_type: "pdf",
  mime_type: "application/pdf",
  size_bytes: 18432,
  status: "ready",
  created_at: timestamp,
  updated_at: timestamp,
}];

const pipeline = {
  pipeline_version_id: DEMO_PIPELINE_ID,
  name: "Evidence review baseline",
  version: 1,
  configuration: { retrieval: "hybrid", reviewer: "strict", dataset: "frozen-demo" },
  code_sha: "demo-static-runtime",
  accepted_at: timestamp,
};

const citation = {
  id: "99999999-9999-4999-8999-999999999999",
  source_type: "local_doc",
  document_id: DEMO_DOCUMENT_ID,
  chunk_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  page_no: 3,
  quote: "Grounding and explicit source attribution make unsupported synthesis visible to reviewers.",
};

const claims = [{
  claim_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  text: "Retrieval improves factual reliability only when the response remains constrained by relevant, cited evidence.",
  stance: "supports",
  confidence: 0.87,
  review_status: "accepted",
  evidence_count: 3,
  support_count: 2,
  contradiction_count: 1,
  duplicate_count: 0,
  source_version: 1,
}];

const relations = [{
  source_claim_id: claims[0].claim_id,
  target_claim_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  relation: "contradicts",
  confidence: 0.64,
  rationale_summary: "A retrieved passage can still be irrelevant or stale; retrieval alone is not a guarantee.",
  source_text: claims[0].text,
  target_text: "Adding retrieval always improves factual correctness.",
}];

const report = {
  report_id: DEMO_REPORT_ID,
  source_run_id: "44444444-4444-4444-8444-444444444444",
  title: "Retrieval reliability evidence review",
  status: "published",
  revision: 1,
  validation_status: "passed",
  affected_section_count: 0,
  generated_at: timestamp,
};

let latestRun: Json = {
  run_id: "44444444-4444-4444-8444-444444444444",
  project_id: DEMO_PROJECT_ID,
  pipeline_version_id: DEMO_PIPELINE_ID,
  kind: "evidence_review",
  status: "succeeded",
  progress: 100,
  current_node: "report_published",
  review_required: false,
  output: { mode: "static-demo", report_id: DEMO_REPORT_ID },
  created_at: timestamp,
  started_at: timestamp,
  completed_at: timestamp,
};

let latestEvaluation: Json = {
  evaluation_run_id: "77777777-7777-4777-8777-777777777777",
  dataset_id: DEMO_DATASET_ID,
  pipeline_version_id: DEMO_PIPELINE_ID,
  status: "succeeded",
  progress: 100,
  summary: { citation_precision: 0.91, evidence_recall: 0.84, schema_valid: 1 },
  scores: [{ metric: "citation_precision", value: 0.91 }, { metric: "evidence_recall", value: 0.84 }, { metric: "schema_valid", value: 1 }],
  created_at: timestamp,
  started_at: timestamp,
  completed_at: timestamp,
};

let quizSets: Json[] = [];

function makeId(prefix: string, sequence: number): string {
  const suffix = sequence.toString(16).padStart(12, "0");
  return `${prefix}0000-0000-4000-8000-${suffix}`;
}

function requestBody(init: globalThis.RequestInit): Json {
  if (typeof init.body !== "string") return {};
  try {
    const parsed = JSON.parse(init.body) as unknown;
    return parsed && typeof parsed === "object" ? parsed as Json : {};
  } catch {
    return {};
  }
}

function projectDocuments(projectId: string): Json[] {
  return documents.filter((document) => document.project_id === projectId);
}

function demoRun(projectId: string, kind: string): Json {
  const id = makeId("44444444-4444", runSequence++);
  latestRun = {
    run_id: id,
    project_id: projectId,
    pipeline_version_id: DEMO_PIPELINE_ID,
    kind,
    status: "succeeded",
    progress: 100,
    current_node: "report_published",
    review_required: false,
    output: { mode: "static-demo", report_id: DEMO_REPORT_ID },
    created_at: timestamp,
    started_at: timestamp,
    completed_at: timestamp,
  };
  return latestRun;
}

/**
 * Public static-demo mode is intentionally a browser-only walkthrough. It has
 * deterministic sample evidence and never sends credentials or requests to a
 * managed API. Real release builds set NEXT_PUBLIC_DEMO_MODE=false.
 */
export function isPublicDemo(): boolean {
  const configured = process.env.NEXT_PUBLIC_DEMO_MODE;
  return configured === "true" || (configured !== "false" && process.env.NODE_ENV === "production");
}

export async function demoFetch<T>(rawPath: string, init: globalThis.RequestInit = {}): Promise<T> {
  const url = new URL(rawPath, "https://demo.invalid");
  const path = url.pathname;
  const method = (init.method ?? "GET").toUpperCase();
  const body = requestBody(init);

  if (path === "/projects" && method === "GET") return projects as T;
  if (path === "/projects" && method === "POST") {
    const id = makeId("11111111-1111", ++projectSequence);
    const next = { id, user_id: "public-demo", name: typeof body.name === "string" && body.name.trim() ? body.name.trim() : "Untitled walkthrough", status: "active", created_at: timestamp, updated_at: timestamp };
    projects.unshift(next);
    return next as T;
  }

  const projectMatch = path.match(/^\/projects\/([^/]+)/);
  const projectId = projectMatch?.[1] ?? DEMO_PROJECT_ID;
  if (path.endsWith("/documents") && method === "GET") return projectDocuments(projectId) as T;
  if (path.endsWith("/claims") && method === "GET") return { items: claims } as T;
  if (path.endsWith("/claim-relations") && method === "GET") return { items: relations } as T;
  if (path.endsWith("/reports") && method === "GET") return { items: [report] } as T;
  if (path.endsWith("/quiz") && method === "GET") return { project_id: projectId, quiz_sets: quizSets } as T;

  if (path === "/documents/upload-url" && method === "POST") {
    const id = makeId("22222222-2222", ++documentSequence);
    documents.push({ id, user_id: "public-demo", project_id: typeof body.project_id === "string" ? body.project_id : DEMO_PROJECT_ID, filename: body.filename ?? "walkthrough-source.pdf", file_type: body.file_type ?? "pdf", mime_type: body.mime_type ?? "application/pdf", size_bytes: body.size_bytes ?? 1, status: "uploading", created_at: timestamp, updated_at: timestamp });
    return { document_id: id, upload_url: `/api/v1/dev/upload/${id}`, expires_in_seconds: 300 } as T;
  }
  const completeMatch = path.match(/^\/documents\/([^/]+)\/complete$/);
  if (completeMatch && method === "POST") {
    const document = documents.find((item) => item.id === completeMatch[1]);
    if (document) document.status = "ready";
    return { document_id: completeMatch[1], status: "ready" } as T;
  }

  if (path === "/pipeline-versions" && method === "GET") return { items: [pipeline] } as T;
  if (path === "/research-runs" && method === "POST") {
    const run = demoRun(typeof body.project_id === "string" ? body.project_id : DEMO_PROJECT_ID, "evidence_review");
    return { run_id: run.run_id, status: "pending", status_url: `/runs/${run.run_id}`, events_url: `/runs/${run.run_id}/events`, created_at: timestamp } as T;
  }
  if (path.startsWith("/runs/") && path.endsWith("/decisions") && method === "POST") return { decision_id: makeId("dddddddd-dddd", runSequence), status: "accepted" } as T;
  if (path.startsWith("/runs/") && method === "GET") return latestRun as T;

  if (path === "/ask" && method === "POST") return {
    run_id: latestRun.run_id,
    answer: "The walkthrough conclusion is conditional: retrieval is useful when evidence is relevant, source-bound, and reviewed; it is not a correctness guarantee by itself.",
    mode: "local_only",
    sources: { local_chunks: 1, web_pages: 0 },
    citations: [citation],
    trace_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    validation_status: "passed",
  } as T;

  if (path.startsWith("/reports/") && path.endsWith("/refresh") && method === "POST") {
    const run = demoRun(DEMO_PROJECT_ID, "report_refresh");
    return { run_id: run.run_id, impacted_section_keys: ["executive-summary"] } as T;
  }
  if (path.startsWith("/reports/") && method === "GET") return {
    ...report,
    sections: [{ section_id: "ffffffff-ffff-4fff-8fff-ffffffffffff", section_key: "executive-summary", position: 1, heading: "Executive summary", body_markdown: "The static walkthrough keeps a complete citation chain visible while the managed Agentic RAG runtime remains separately marked as unvalidated.", evidence_snapshot: { citations: [citation.id] }, validation_status: "passed" }],
  } as T;

  if (path === "/quiz" && method === "POST") {
    quizSets = [{ id: "12121212-1212-4212-8212-121212121212", mode: "local_only", sources: { local_chunks: 1, web_pages: 0 }, questions: [{ id: "13131313-1313-4313-8313-131313131313", type: "single_choice", question: "What makes a retrieved conclusion defensible?", options: ["A larger prompt", "A citation-backed relevant source", "A longer answer", "An unbounded web search"], answer: "A citation-backed relevant source", explanation: "The walkthrough records a claim-to-citation relationship rather than treating retrieval as a correctness guarantee.", difficulty: "easy", source_citations: [citation] }] }];
    return quizSets[0] as T;
  }

  if (path === "/evaluation-datasets" && method === "GET") return { items: [{ dataset_id: DEMO_DATASET_ID, project_id: DEMO_PROJECT_ID, name: "Frozen walkthrough set", version: 1, description: "Deterministic examples for the public demo.", case_count: 3 }] } as T;
  if (path === "/evaluation-runs" && method === "POST") {
    const id = makeId("77777777-7777", ++evaluationSequence);
    latestEvaluation = { ...latestEvaluation, evaluation_run_id: id, created_at: timestamp };
    return { evaluation_run_id: id, case_count: 3, status_url: `/evaluation-runs/${id}`, estimated_budget_boundary: "0.00" } as T;
  }
  if (path.startsWith("/evaluation-runs/") && method === "GET") return latestEvaluation as T;
  if (path === "/dev/reliability" && method === "GET") return { window_hours: Number(url.searchParams.get("window_hours") ?? 24), run_count: 4, success_rate: 1, error_rate: 0, retry_count: 1, p50_latency_ms: 120, p95_latency_ms: 240, input_tokens: 0, output_tokens: 0, cost_usd: "0.0000", sample_trace_ids: ["eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"] } as T;
  if (path === "/dev/fault-scenarios" && method === "POST") return { exercise_id: "14141414-1414-4414-8414-141414141414", expected_recovery_state: "simulated; canonical state unchanged", expires_at: "2026-07-19T08:00:10.000Z" } as T;
  if (path.startsWith("/dev/traces/") && method === "GET") return { trace_id: path.split("/").at(-1), user_id: "public-demo", project_id: DEMO_PROJECT_ID, run_id: latestRun.run_id, execution_plan: { mode: "static-demo" }, router_reason: "No external provider called.", retrieved_chunks: [citation], tool_calls: [], validation_result: { status: "passed" }, created_at: timestamp } as T;

  throw new Error(`Static demo does not implement ${method} ${path}.`);
}

export async function demoRunEvents(onEvent: (event: DemoRunEvent) => void, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return;
  [
    { event_id: 1, sequence: 1, node_key: "retrieve", event_type: "retrieval_completed", attempt: 1, status: "succeeded", safe_payload: { demo: true }, latency_ms: 120, created_at: timestamp },
    { event_id: 2, sequence: 2, node_key: "report", event_type: "report_published", attempt: 1, status: "succeeded", safe_payload: { demo: true }, latency_ms: 240, created_at: timestamp },
  ].forEach((event) => onEvent(event));
}
