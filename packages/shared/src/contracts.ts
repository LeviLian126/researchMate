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
  document_id?: string;
  chunk_id?: string;
  page_no?: number;
  slide_no?: number;
  url?: string;
  quote: string;
  claim_id?: string;
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

// 定义 Quiz 题目结构。
export interface QuizQuestion {
  id: string;
  type: "single_choice" | "short_answer";
  question: string;
  options?: string[];
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

// 定义统一错误响应。
export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    request_id: string;
  };
}

