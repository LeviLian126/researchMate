"""Assemble the FastAPI application, adapters, middleware, and error boundaries."""

from __future__ import annotations

import re
import signal
from collections.abc import Callable
from contextlib import asynccontextmanager
from time import monotonic
from typing import Any, cast
from uuid import UUID, uuid4

from anyio import to_thread
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from researchmate_api.config import Settings, get_settings
from researchmate_api.dependencies import resolve_bearer_token
from researchmate_api.mcp_server import MCPRequestIdentity, current_mcp_identity
from researchmate_api.observability import configure_observability, log_event
from researchmate_api.persistence._postgres_core import (
    ObjectMetadataReader,
    UploadUrlFactory,
)
from researchmate_api.routers import (
    ask,
    conversations,
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
from researchmate_api.schemas.common import ErrorResponse
from researchmate_api.schemas.document import UploadUrlRequest
from researchmate_api.services.embedding import NvidiaEmbeddingProvider
from researchmate_api.services.evidence_store import EvidenceRepository, InMemoryEvidenceRepository
from researchmate_api.services.llm import NvidiaChatProvider
from researchmate_api.services.object_storage import S3CompatibleObjectStorage, StoredObjectMetadata
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.rerank import RerankCoordinator
from researchmate_api.services.store import InMemoryResearchMateStore, ResearchMateRepository
from researchmate_api.services.web_search import TavilyWebSearchProvider

# Rate limiting is an optional dependency: environments without slowapi still start, they just
# skip the in-process limiter. This mirrors the optional MCP SDK import pattern below.
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
except ModuleNotFoundError as exc:  # pragma: no cover - optional adapter surface.
    if exc.name is None or not exc.name.startswith("slowapi"):
        raise
    Limiter = None  # type: ignore[assignment]
    _rate_limit_exceeded_handler = None  # type: ignore[assignment]
    RateLimitExceeded = None  # type: ignore[assignment]
    get_remote_address = None  # type: ignore[assignment]

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{4,120}$")
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # Lock down content sources and require HTTPS for a year on every subdomain.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

# Public, low-cost endpoints (health probes and authentication) are bounded to a generous
# per-IP ceiling to blunt brute-force and abuse while leaving normal interactive traffic alone.
RATE_LIMIT_PER_MINUTE = "60/minute"
# Paths that share the IP-based rate-limit bucket. Auth paths are included because they are
# the primary brute-force surface; health probes because they are unauthenticated and cheap.
RATE_LIMITED_PATHS = frozenset(
    {
        "/api/v1/healthz",
        "/api/v1/readyz",
        # Authentication edge endpoints.
        "/api/v1/me",
        "/mcp",
    }
)

# INFRA-3: graceful-shutdown window. This mirrors the worker soft time limit (840s) so a
# request or MCP session mid-flight is not torn down by the platform default 20s window.
# The actual enforcement lives on the ASGI server (uvicorn --timeout-graceful-shutdown),
# which is set by render_combined.child_commands. This constant is the single in-process
# source of truth so any future in-process drain logic stays aligned with that window.
GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 840

# Module-level flag flipped by the SIGTERM/SIGINT handler below. Components that perform
# long-running work in-process may poll this flag to opt into an early checkpoint instead of
# waiting for the OS to deliver the signal at the end of the window.
_SHUTTING_DOWN: bool = False


def _handle_shutdown_signal(signum: int, _frame: object) -> None:
    """Flip the in-process shutdown flag for observability and cooperative drain.

    This handler intentionally does NOT raise or sys.exit: the actual graceful-shutdown
    window is enforced by the ASGI server (uvicorn --timeout-graceful-shutdown). Flipping
    this flag only lets long-running in-process work observe the signal and checkpoint
    early instead of holding resources up to the platform-enforced ceiling.
    """
    global _SHUTTING_DOWN
    _SHUTTING_DOWN = True
    log_event(
        "shutdown_signal_received",
        signal=signal.Signals(signum).name,
        graceful_timeout_seconds=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,
    )


def _register_shutdown_handlers() -> None:
    """Register SIGTERM and SIGINT handlers that observe the shutdown transition.

    Windows has no SIGTERM (it only defines SIGINT), so SIGTERM registration is skipped on
    that platform. uvicorn still receives the signal when run as a child process under the
    supervisor, so the ASGI-level graceful window applies regardless.
    """
    # Skip re-registration if the signals are unsupported on this platform (Windows only
    # exposes SIGINT) so importing this module never raises in test/dev environments.
    sigterm = getattr(signal, "SIGTERM", None)
    if sigterm is not None:
        try:
            signal.signal(sigterm, _handle_shutdown_signal)
        except (ValueError, OSError):
            # ValueError is raised when not in the main thread; OSError when the signal
            # cannot be installed. Failing open keeps the import path non-fatal.
            pass
    try:
        signal.signal(signal.SIGINT, _handle_shutdown_signal)
    except (ValueError, OSError):
        pass


# Register the observer handlers at import time so a SIGTERM/SIGINT delivered to the API
# process (whether from the platform or the render_combined supervisor) is logged and the
# in-process flag flips. The ASGI server still owns the actual shutdown-window enforcement.
_register_shutdown_handlers()


def create_app(
    settings: Settings | None = None,
    repository: ResearchMateRepository | None = None,
    evidence_repository: EvidenceRepository | None = None,
) -> FastAPI:
    """Create the API application with explicit adapters and an optional MCP surface."""
    runtime_settings = settings or get_settings()
    observability = None
    mcp_server = None
    mcp_asgi = None
    try:
        from researchmate_api.mcp_server import build_mcp_server

        mcp_server, mcp_asgi = build_mcp_server()
    except ModuleNotFoundError as exc:
        if exc.name is None or not exc.name.startswith("mcp"):
            raise

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        """Own MCP session and observability shutdown lifecycles."""
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
            502: {"model": ErrorResponse, "description": "Provider output was invalid"},
            503: {"model": ErrorResponse, "description": "Dependency unavailable"},
        },
    )
    app.state.settings = runtime_settings
    app.state.object_storage = (
        S3CompatibleObjectStorage(runtime_settings)
        if runtime_settings.object_storage_configured
        else None
    )
    app.state.store = repository or build_repository(
        runtime_settings, object_storage=app.state.object_storage
    )
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
    app.state.reranker = RerankCoordinator(
        runtime_settings,
        qdrant=app.state.hybrid_store,
    )
    if runtime_settings.web_search_provider == "tavily":
        app.state.web_search = TavilyWebSearchProvider(runtime_settings)
    observability = configure_observability(app, runtime_settings)
    # Configure IP-based rate limiting for the cheap public endpoints and the auth edge.
    # When the optional slowapi dependency is not installed the limiter is absent so that
    # local development and worker environments can still bootstrap the API surface.
    if Limiter is not None:
        from limits import parse as _parse_rate_limit

        # The slowapi symbols are typed as `X | None` at module scope because the optional
        # import falls back to None when slowapi is absent. Inside this branch slowapi is
        # installed, so assert each symbol to its non-None form for the slowapi API surface.
        assert get_remote_address is not None
        assert _rate_limit_exceeded_handler is not None
        assert RateLimitExceeded is not None
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[],
            headers_enabled=True,
        )
        app.state.limiter = limiter
        # Pre-parse the rate limit once so every request shares the same RateLimitItem and the
        # per-IP window is a single fixed-window bucket across all RATE_LIMITED_PATHS.
        app.state.rate_limit_item = _parse_rate_limit(RATE_LIMIT_PER_MINUTE)
        # The slowapi handler signature is a coroutine but FastAPI's stubs declare
        # ExceptionHandler as a sync callable. Cast through Any so the runtime contract
        # (which FastAPI supports) is preserved without fighting the stub typing.
        app.add_exception_handler(  # type: ignore[arg-type]
            RateLimitExceeded,
            cast(Any, _rate_limit_exceeded_handler),
        )
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
        """Attach correlation/security headers and authenticate MCP without blocking the loop."""
        started = monotonic()
        response_status = 500
        candidate = request.headers.get(runtime_settings.request_id_header, "")
        request_id = candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else f"req_{uuid4().hex}"
        request.state.request_id = request_id

        # IP-based rate limit check for cheap public endpoints and the auth edge. The bucket
        # is shared per source IP across the configured protected paths. When slowapi is not
        # installed this branch is skipped entirely and the API still serves requests.
        limiter = getattr(request.app.state, "limiter", None)
        rate_limit_item = getattr(request.app.state, "rate_limit_item", None)
        if (
            limiter is not None
            and rate_limit_item is not None
            and request.url.path in RATE_LIMITED_PATHS
        ):
            # get_remote_address is the slowapi resolver; the optional-import path leaves it as
            # None at module scope. The block above only enters when slowapi is installed, so
            # narrow the resolver via cast for the per-IP bucket assignment.
            client_ip = cast(Callable[[Request], str], get_remote_address)(request) or "unknown"
            bucket_scope = "researchmate-api:protected"
            allowed = limiter._limiter.hit(  # type: ignore[attr-defined]
                rate_limit_item, client_ip, bucket_scope, cost=1
            )
            if not allowed:
                response_status = 429
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Rate limit exceeded. Try again later.",
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
            user = await to_thread.run_sync(
                resolve_bearer_token,
                authorization[7:].strip(),
                runtime_settings,
            )
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
            await to_thread.run_sync(app.state.store.ensure_user, user)
            context_token = current_mcp_identity.set(
                MCPRequestIdentity(
                    user=user,
                    repository=app.state.store,
                    evidence=app.state.evidence_store,
                    chat_provider=app.state.chat_provider,
                    hybrid_store=app.state.hybrid_store,
                    web_search=app.state.web_search,
                    settings=runtime_settings,
                    reranker=app.state.reranker,
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

    # FastAPI accepts coroutines for exception handlers but its type stubs declare
    # ExceptionHandler as sync. The runtime contract is preserved by casting the
    # coroutine function to the typed handler slot.
    # FastAPI accepts coroutine functions for exception handlers but its type stubs declare
    # ExceptionHandler as a sync signature. Cast the coroutine functions through Any so the
    # runtime contract (which FastAPI supports) is preserved without fighting the stub.
    app.add_exception_handler(  # type: ignore[arg-type]
        HTTPException,
        cast(Any, http_exception_handler),
    )
    app.add_exception_handler(  # type: ignore[arg-type]
        RequestValidationError,
        cast(Any, validation_exception_handler),
    )
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(me.router, prefix="/api/v1", tags=["auth"])
    app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
    app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
    app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
    app.include_router(ask.router, prefix="/api/v1", tags=["ask"])
    app.include_router(conversations.router, prefix="/api/v1", tags=["conversations"])
    app.include_router(quiz.router, prefix="/api/v1", tags=["quiz"])
    app.include_router(runs.router, prefix="/api/v1", tags=["sources"])
    app.include_router(dev_traces.router, prefix="/api/v1", tags=["developer-trace"])
    app.include_router(evidence.router, prefix="/api/v1", tags=["evidence-review"])
    if mcp_asgi is not None:
        app.mount("/mcp", mcp_asgi)
    else:

        @app.api_route("/mcp", methods=["GET", "POST", "DELETE"], include_in_schema=False)
        async def mcp_dependency_unavailable(request: Request):
            """Return an authenticated, explicit error when the optional MCP SDK is absent."""
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


def build_repository(
    settings: Settings,
    *,
    object_storage: S3CompatibleObjectStorage | None = None,
) -> ResearchMateRepository:
    """Build the configured persistence adapter without opening a database connection."""
    if settings.repository_backend == "memory":
        return InMemoryResearchMateStore()

    from researchmate_api.persistence.postgres import PostgresResearchMateRepository
    assert settings.database_url is not None
    # Typed factories are constructed lazily when object storage is configured so that local and
    # worker environments without S3-like storage still bootstrap the repository. Both names are
    # assigned None initially and conditionally rebound to closure callables; the casts at the
    # binding site preserve the factory types through the optional binding.
    upload_url_factory: UploadUrlFactory | None = None
    object_metadata_reader: ObjectMetadataReader | None = None
    if settings.object_storage_configured:
        storage = object_storage or S3CompatibleObjectStorage(settings)

        def _upload_url_factory(
            document_id: UUID, _object_key: str, _payload: UploadUrlRequest
        ) -> str:
            """Route browser uploads through the authenticated same-origin API boundary."""
            return f"/api/v1/documents/{document_id}/content"

        def _object_metadata_reader(
            object_key: str, *, declared_mime_type: str | None = None
        ) -> StoredObjectMetadata:
            """Read object metadata and verify uploaded magic bytes match the declared MIME.

            When the caller supplies the declared MIME type (set by the upload reservation),
            the server downloads the first chunk of the stored object and runs libmagic to
            confirm the bytes really are the declared type. The upload is rejected (and the
            object deleted) on a mismatch so private storage never retains disguised content.
            """
            metadata = storage.head(object_key)
            if declared_mime_type is not None:
                storage.verify_uploaded_content(object_key, declared_mime_type=declared_mime_type)
            return metadata

        # Reassign the optional factory names with cast so the inferred callable shapes widen
        # back to the declared factory types instead of shadowing the typed outer declaration.
        upload_url_factory = cast(UploadUrlFactory, _upload_url_factory)
        object_metadata_reader = cast(ObjectMetadataReader, _object_metadata_reader)

    return cast(
        ResearchMateRepository,
        PostgresResearchMateRepository.from_database_url(
            settings.database_url,
            default_project_ttl_days=settings.default_project_ttl_days,
            upload_url_factory=upload_url_factory,
            object_metadata_reader=object_metadata_reader,
        ),
    )


def build_evidence_repository(settings: Settings) -> EvidenceRepository:
    """Build the evidence-workflow repository selected by runtime configuration."""
    if settings.repository_backend == "memory":
        return InMemoryEvidenceRepository()
    from researchmate_api.persistence.evidence_postgres import PostgresEvidenceRepository

    assert settings.database_url is not None
    return cast(
        EvidenceRepository,
        PostgresEvidenceRepository.from_database_url(settings.database_url),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Map HTTP exceptions to the stable public error envelope."""
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


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Expose only safe field paths and error types for validation failures."""
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
