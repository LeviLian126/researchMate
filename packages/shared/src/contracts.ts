// 定义资料来源模式，Mode 只决定从哪里取证据。
export type SourceMode = "auto" | "local_only" | "web_only" | "hybrid";

// 定义任务类型，Task 只决定要做什么。
export type TaskType = "answer" | "quiz";

// 定义可调用工具名称，后端根据 ExecutionPlan 控制工具边界。
export type ToolName =
  | "query_local_docs"
  | "search_web"
  | "read_url"
  | "crawl_url_optional"
  | "evidence_fusion"
  | "generate_answer"
  | "generate_quiz"
  | "save_quiz";

// 定义一次请求解析后的执行计划。
export interface ExecutionPlan {
  source_mode: SourceMode;
  task_type: TaskType;
  allowed_tools: ToolName[];
  requires_local_docs: boolean;
  requires_web: boolean;
  output_schema: "GroundedAnswer" | "QuizSet";
}

// 定义回答顶部的来源摘要。
export interface SourceSummary {
  local_chunks: number;
  web_pages: number;
}

// 定义本地或网络证据引用。
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

// 定义可溯源回答的结构化输出。
export interface GroundedAnswer {
  mode: SourceMode;
  sources: SourceSummary;
  answer: string;
  citations: Citation[];
  trace_id: string;
  validation_status: "passed" | "failed" | "retrying";
}

// 定义 Ask API 响应。
export interface AskResponse extends GroundedAnswer {
  run_id: string;
}

// 定义 Quiz 题目结构。
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

// 定义 QuizSet 结构化输出。
export interface QuizSet {
  id: string;
  mode: SourceMode;
  sources: SourceSummary;
  questions: QuizQuestion[];
}

// 定义 Quiz 历史响应。
export interface QuizHistoryResponse {
  project_id: string;
  quiz_sets: QuizSet[];
}

// 定义项目记录。
export interface ProjectRecord {
  id: string;
  user_id: string;
  name: string;
  status: "active" | "deleting" | "deleted" | "expired" | string;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}

// 定义文档状态。
export type DocumentStatus =
  | "uploaded"
  | "parsing"
  | "parsed"
  | "indexing"
  | "ready"
  | "failed"
  | "expired"
  | "deleted";

// 定义文档记录。
export interface DocumentRecord {
  id: string;
  user_id: string;
  project_id: string;
  filename: string;
  file_type: "pdf" | "docx" | "pptx" | string;
  mime_type: string;
  size_bytes: number;
  status: DocumentStatus;
  error_message?: string | null;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}

// 定义上传地址请求。
export interface UploadUrlRequest {
  project_id: string;
  filename: string;
  file_type: "pdf" | "docx" | "pptx";
  mime_type: string;
  size_bytes: number;
}

// 定义本地开发上传完成请求。
export interface UploadCompleteRequest {
  checksum_sha256?: string | null;
  extracted_text?: string | null;
}

// 定义上传地址响应。
export interface UploadUrlResponse {
  document_id: string;
  upload_url: string;
  r2_object_key: string;
  expires_in_seconds: number;
}

// 定义 job 状态。
export interface JobRecord {
  id: string;
  user_id: string;
  project_id?: string | null;
  document_id?: string | null;
  type: string;
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

// 定义 Developer Trace。
export interface DeveloperTrace {
  trace_id: string;
  user_id: string;
  project_id: string;
  run_id: string;
  execution_plan: ExecutionPlan;
  router_reason: string;
  retrieved_chunks: Record<string, unknown>[];
  tool_calls: Record<string, unknown>[];
  validation_result: Record<string, unknown>;
  created_at: string;
}

// 定义统一错误响应。
export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    request_id: string;
  };
}
