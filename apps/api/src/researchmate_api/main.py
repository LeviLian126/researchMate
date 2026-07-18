import re
from time import monotonic
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from researchmate_api.config import Settings, get_settings
from researchmate_api.dependencies import resolve_bearer_token
from researchmate_api.mcp_server import MCPRequestIdentity, current_mcp_identity
from researchmate_api.observability import configure_observability, log_event
from researchmate_api.schemas.common import ErrorResponse
from researchmate_api.routers import (
    ask,
    dev_traces,
    documents,
    evidence,
    health,
    jobs,
    me,
    projects,
    quiz,
    runs,
)
from researchmate_api.services.evidence_store import EvidenceRepository, InMemoryEvidenceRepository
from researchmate_api.services.store import InMemoryResearchMateStore, ResearchMateRepository
from researchmate_api.services.llm import NvidiaChatProvider
from researchmate_api.services.embedding import NvidiaEmbeddingProvider
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.web_search import TavilyWebSearchProvider


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{4,120}$")
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


# 创建 FastAPI 应用并注册业务路由。
def create_app(
    settings: Settings | None = None,
    repository: ResearchMateRepository | None = None,
    evidence_repository: EvidenceRepository | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    observability = None
    mcp_server = None
    mcp_asgi = None
    try:
        from researchmate_api.mcp_server import build_mcp_server

        mcp_server, mcp_asgi = build_mcp_server()
    except ImportError:
        pass

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            if mcp_server is None:
                yield
            else:
                async with mcp_server.session_manager.run():
                    yield
        finally:
            if observability is not None:
                observability.shutdown()

    app = FastAPI(
        title="ResearchMate API",
        version="0.1.0",
        description="Local-first ResearchMate API with swappable cloud/provider adapters.",
        lifespan=lifespan,
        responses={
            400: {"model": ErrorResponse, "description": "Invalid request"},
            401: {"model": ErrorResponse, "description": "Authentication required"},
            403: {"model": ErrorResponse, "description": "Permission denied"},
            404: {"model": ErrorResponse, "description": "Resource not found"},
            409: {"model": ErrorResponse, "description": "State or idempotency conflict"},
            422: {"model": ErrorResponse, "description": "Request validation failed"},
            429: {"model": ErrorResponse, "description": "Usage limit exceeded"},
            503: {"model": ErrorResponse, "description": "Dependency unavailable"},
        },
    )
    app.state.settings = runtime_settings
    app.state.store = repository or build_repository(runtime_settings)
    app.state.evidence_store = evidence_repository or build_evidence_repository(runtime_settings)
    app.state.chat_provider = (
        NvidiaChatProvider(runtime_settings) if runtime_settings.llm_provider == "nvidia" else None
    )
    app.state.hybrid_store = None
    app.state.web_search = None
    if (
        runtime_settings.embedding_provider == "nvidia"
        and runtime_settings.qdrant_url
        and runtime_settings.qdrant_api_key is not None
    ):
        app.state.hybrid_store = QdrantHybridStore(
            runtime_settings,
            NvidiaEmbeddingProvider(runtime_settings),
        )
    if runtime_settings.web_search_provider == "tavily":
        app.state.web_search = TavilyWebSearchProvider(runtime_settings)
    observability = configure_observability(app, runtime_settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-ID",
            "Mcp-Session-Id",
            "Last-Event-ID",
        ],
        expose_headers=["X-Request-ID", "Mcp-Session-Id"],
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        started = monotonic()
        response_status = 500
        candidate = request.headers.get(runtime_settings.request_id_header, "")
        request_id = candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else f"req_{uuid4().hex}"
        request.state.request_id = request_id
        context_token = None
        if request.url.path == "/mcp" or request.url.path.startswith("/mcp/"):
            authorization = request.headers.get("Authorization", "")
            if not authorization.startswith("Bearer "):
                response_status = 401
                response = JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "AUTH_REQUIRED",
                            "message": "Bearer token is required.",
                            "request_id": request_id,
                        }
                    },
                )
                response.headers["X-Request-ID"] = request_id
                for name, value in SECURITY_HEADERS.items():
                    response.headers[name] = value
                log_event(
                    "http_request_completed",
                    request_id=request_id,
                    method=request.method,
                    route=request.url.path,
                    status_code=response_status,
                    latency_ms=round((monotonic() - started) * 1000),
                    environment=runtime_settings.app_env,
                )
                return response
            user = resolve_bearer_token(authorization[7:].strip(), runtime_settings)
            if user is None:
                response_status = 401
                response = JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "INVALID_TOKEN",
                            "message": "Bearer token is invalid.",
                            "request_id": request_id,
                        }
                    },
                )
                response.headers["X-Request-ID"] = request_id
                for name, value in SECURITY_HEADERS.items():
                    response.headers[name] = value
                log_event(
                    "http_request_completed",
                    request_id=request_id,
                    method=request.method,
                    route=request.url.path,
                    status_code=response_status,
                    latency_ms=round((monotonic() - started) * 1000),
                    environment=runtime_settings.app_env,
                )
                return response
            app.state.store.ensure_user(user)
            context_token = current_mcp_identity.set(
                MCPRequestIdentity(
                    user=user,
                    repository=app.state.store,
                    evidence=app.state.evidence_store,
                    chat_provider=app.state.chat_provider,
                    hybrid_store=app.state.hybrid_store,
                    web_search=app.state.web_search,
                )
            )
        try:
            response = await call_next(request)
            response_status = response.status_code
            response.headers["X-Request-ID"] = request_id
            for name, value in SECURITY_HEADERS.items():
                response.headers[name] = value
            return response
        finally:
            if context_token is not None:
                current_mcp_identity.reset(context_token)
            log_event(
                "http_request_completed",
                request_id=request_id,
                method=request.method,
                route=request.url.path,
                status_code=response_status,
                latency_ms=round((monotonic() - started) * 1000),
                environment=runtime_settings.app_env,
            )

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(me.router, prefix="/api/v1", tags=["auth"])
    app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
    app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
    app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
    app.include_router(ask.router, prefix="/api/v1", tags=["ask"])
    app.include_router(quiz.router, prefix="/api/v1", tags=["quiz"])
    app.include_router(runs.router, prefix="/api/v1", tags=["sources"])
    app.include_router(dev_traces.router, prefix="/api/v1", tags=["developer-trace"])
    app.include_router(evidence.router, prefix="/api/v1", tags=["evidence-review"])
    if mcp_asgi is not None:
        app.mount("/mcp", mcp_asgi)
    else:
        @app.api_route("/mcp", methods=["GET", "POST", "DELETE"], include_in_schema=False)
        async def mcp_dependency_unavailable(request: Request):
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "MCP_RUNTIME_NOT_INSTALLED",
                        "message": "Install the pinned MCP SDK to enable Streamable HTTP.",
                        "request_id": getattr(request.state, "request_id", "req_mcp_unavailable"),
                    }
                },
            )
    return app


def build_repository(settings: Settings) -> ResearchMateRepository:
    """Build the configured persistence adapter without opening a database connection."""
    if settings.repository_backend == "memory":
        return InMemoryResearchMateStore()

    from researchmate_api.persistence.postgres import PostgresResearchMateRepository
    from researchmate_api.services.object_storage import R2ObjectStorage

    assert settings.database_url is not None
    upload_url_factory = None
    object_metadata_reader = None
    if settings.r2_configured:
        storage = R2ObjectStorage(settings)

        def upload_url_factory(_document_id, object_key, payload):
            return storage.presign_upload(object_key, content_type=payload.mime_type)

        object_metadata_reader = storage.head
    return PostgresResearchMateRepository.from_database_url(
        settings.database_url,
        default_project_ttl_days=settings.default_project_ttl_days,
        upload_url_factory=upload_url_factory,
        object_metadata_reader=object_metadata_reader,
    )


def build_evidence_repository(settings: Settings) -> EvidenceRepository:
    if settings.repository_backend == "memory":
        return InMemoryEvidenceRepository()
    from researchmate_api.persistence.evidence_postgres import PostgresEvidenceRepository

    assert settings.database_url is not None
    return PostgresEvidenceRepository.from_database_url(settings.database_url)


# 将 HTTPException 转成统一错误体，避免泄露 stack trace。
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and {"code", "message", "request_id"} <= set(exc.detail):
        payload = dict(exc.detail)
    else:
        payload = {
            "code": "HTTP_ERROR",
            "message": str(exc.detail),
            "request_id": getattr(request.state, "request_id", "req_unavailable"),
        }
    payload["request_id"] = getattr(request.state, "request_id", payload["request_id"])
    return JSONResponse(status_code=exc.status_code, content={"error": payload})


# 将请求校验错误转成统一错误体，只暴露字段路径和错误类型。
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"loc": [str(part) for part in error.get("loc", [])], "type": error.get("type")}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_FAILED",
                "message": f"Request validation failed: {errors}",
                "request_id": getattr(request.state, "request_id", "req_unavailable"),
            }
        },
    )


app = create_app()
