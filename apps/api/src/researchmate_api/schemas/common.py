"""Define shared API enums, identity models, citations, and execution plans."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Maximum length for any user-visible text snippet (citations, claims, quiz
# questions, rerank/query inputs truncated to this size). Centralizing this
# avoids magic-number drift across schema validation and storage layers.
MAX_TEXT_LENGTH = 1200

# Centralize the context-strategy literal so callers in services layers can
# reference it without duplicating the schema-defined member list.
ContextStrategy = Literal[
    "chat",
    "full_context",
    "hybrid_retrieval",
    "web",
    "hybrid_retrieval_web",
    "quiz",
]

# Message and content length limits. Centralizing these keeps schema
# validation, response contracts, and storage layers aligned without
# magic-number drift across modules.
MAX_MESSAGE_LENGTH = 8000
MAX_ANSWER_LENGTH = 16000
MAX_CONVERSATION_MESSAGE_LENGTH = 16000
MAX_DOCUMENT_CONTENT_LENGTH = 200_000
MAX_PROMPT_LENGTH = 4000
MAX_REASON_LENGTH = 2000
MAX_EVIDENCE_TEXT_LENGTH = 1600
MAX_ID_LENGTH = 120
MAX_FALLBACK_REASON_LENGTH = 300
MAX_FEEDBACK_COMMENT_LENGTH = 1000

# Snippet lengths. Each constant names the bounded excerpt size used by a
# specific call site so retrieval and quiz generation share one source of
# truth instead of divergent hardcoded literals.
SNIPPET_DEFAULT = 280
SNIPPET_CHUNK = 900
SNIPPET_QUOTE_SHORT = 180
SNIPPET_QUOTE_MEDIUM = 220
SNIPPET_QUOTE_LONG = 260

# Token threshold at or below which a document is classified as lightweight.
# Lightweight documents skip embedding and Qdrant upsert during ingestion and
# are always injected directly into the query context.
LIGHTWEIGHT_DOCUMENT_TOKEN_THRESHOLD_DEFAULT = 4000

# Wiki compilation bounds. Lightweight documents below the token threshold are
# eligible for LLM-powered wiki compilation. These constants bound the compiler
# output so generated wiki pages stay within storage and context limits.
WIKI_MAX_PAGES = 8
WIKI_MAX_TITLE_LENGTH = 200
WIKI_MAX_CONTENT_LENGTH = 8000
WIKI_MAX_ALIASES = 10
WIKI_MAX_LINKS = 20
WIKI_MAX_SOURCE_CHUNKS = 20
WIKI_PAGE_TYPE_LENGTH = 50

# Maximum input token budget for overview Wiki compilation of long documents.
# Long documents exceed the lightweight threshold and are embedded into Qdrant;
# overview Wiki compilation selects a representative subset of their chunks to
# summarize into an overview page without exceeding the LLM context window.
WIKI_OVERVIEW_MAX_INPUT_TOKENS = 6000
WIKI_PLANNER_CONTENT_LENGTH = 1200
WIKI_MAX_ENTITIES = 64
WIKI_MAX_CLAIMS = 128
WIKI_MAX_RELATIONS = 128
WIKI_MAX_SUMMARY_LENGTH = 4000
WIKI_MAX_CLAIM_PART_LENGTH = 1000
WIKI_MAX_DELTA_SOURCE_CHUNKS = 512
WIKI_CANONICAL_TOKEN_OVERLAP = 0.8

# Developer-trace bounds. Each limit constrains an admin-visible diagnostic
# field so trace payloads stay privacy-bounded and storage-stable.
MAX_TOOL_NAME_LENGTH = 120
MAX_ERROR_MESSAGE_LENGTH = 500
MAX_ROUTER_REASON_LENGTH = 2000
MAX_RETRIEVED_CHUNKS_SUMMARY = 80
MAX_TOOL_CALLS_SUMMARY = 40
MAX_ERRORS_SUMMARY = 20
MIN_LATENCY_MS = 0

# Evidence workflow bounds. These constrain research runs, human decisions,
# pipeline configuration, evaluation runs, and fault exercises against a
# shared source of truth so backend services and storage layers stay aligned.
MIN_RESEARCH_GOAL_LENGTH = 20
MAX_RESEARCH_GOAL_LENGTH = 12_000
MAX_COST_USD = 25
MAX_DOCUMENT_IDS_LENGTH = 200
MIN_INTERRUPT_KEY_LENGTH = 1
MAX_INTERRUPT_KEY_LENGTH = 160
MAX_FORCE_SECTIONS_LENGTH = 100
MIN_METRICS_LENGTH = 1
MAX_METRICS_LENGTH = 6
MIN_MAX_PARALLELISM = 1
MAX_MAX_PARALLELISM = 20
MIN_DURATION_SECONDS = 1
MAX_DURATION_SECONDS = 60

# Document upload bounds. These constrain upload metadata and reservation
# responses so clients and storage backends share one source of truth.
MAX_UPLOAD_FILENAME_LENGTH = 240
MIN_UPLOAD_MIME_TYPE_LENGTH = 3
MAX_UPLOAD_MIME_TYPE_LENGTH = 120
MIN_UPLOAD_URL_LENGTH = 1
MAX_UPLOAD_URL_LENGTH = 4096
MIN_R2_OBJECT_KEY_LENGTH = 16
MAX_R2_OBJECT_KEY_LENGTH = 512
MIN_UPLOAD_EXPIRES_IN_SECONDS = 60
MAX_UPLOAD_EXPIRES_IN_SECONDS = 900

# Quiz content bounds. These constrain topic queries, single-choice options,
# and per-question explanations so quiz generation respects LLM context limits.
MAX_TOPIC_QUERY_LENGTH = 1000
MAX_QUIZ_OPTIONS_LENGTH = 4
MAX_QUIZ_EXPLANATION_LENGTH = 2000


# Define task types. Task only controls the execution goal.
class TaskType(str, Enum):
    """Select the high-level operation requested from the query pipeline."""

    ANSWER = "answer"
    QUIZ = "quiz"


# Define document status. Subsequent workers may only advance along this state machine.
class DocumentStatus(str, Enum):
    """Enumerate durable document-ingestion lifecycle states."""

    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"
    DELETED = "deleted"


# Define asynchronous job status.
class JobStatus(str, Enum):
    """Enumerate asynchronous job lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Define citation source types.
class SourceType(str, Enum):
    """Identify whether cited evidence is local or web-derived."""

    LOCAL_DOC = "local_doc"
    WEB_PAGE = "web_page"


# Define quiz difficulty.
class Difficulty(str, Enum):
    """Constrain quiz difficulty to supported levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# Define the unified error body.
class ErrorDetail(BaseModel):
    """Represent the stable machine and human fields of an API error."""

    code: str = Field(min_length=2, max_length=80)
    message: str = Field(min_length=1, max_length=300)
    request_id: str = Field(min_length=4, max_length=120)


# Define the unified error response.
class ErrorResponse(BaseModel):
    """Wrap API error details in the public response envelope."""

    error: ErrorDetail


# Define the current authenticated user.
class CurrentUser(BaseModel):
    """Represent the authenticated identity passed across API boundaries."""

    id: UUID
    email: str | None = Field(default=None, max_length=320)
    role: Literal["user", "developer", "admin"] = "user"


# Define the top-of-answer source summary.
class SourceSummary(BaseModel):
    """Summarize the evidence mix returned with an answer."""

    local_chunks: int = Field(default=0, ge=0, le=50)
    web_pages: int = Field(default=0, ge=0, le=20)


# Define the shared citation structure for answers and quizzes.
class Citation(BaseModel):
    """Represent a server-validated evidence reference exposed to clients."""

    id: UUID
    source_type: SourceType
    document_id: UUID | None = None
    chunk_id: UUID | None = None
    page_no: int | None = Field(default=None, ge=1)
    slide_no: int | None = Field(default=None, ge=1)
    section_title: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=2048)
    quote: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    claim_id: str | None = Field(default=None, max_length=120)

    model_config = ConfigDict(use_enum_values=True)


# Define the execution plan resolved on the server for the unified chat entry point.
class ExecutionPlan(BaseModel):
    """Describe the bounded server-side plan selected for a query."""

    task_type: TaskType
    allowed_tools: list[str] = Field(min_length=1, max_length=12)
    requires_local_docs: bool
    requires_web: bool
    context_strategy: ContextStrategy
    output_schema: Literal["ChatAnswer", "GroundedAnswer", "QuizSet"]

    model_config = ConfigDict(use_enum_values=True)
