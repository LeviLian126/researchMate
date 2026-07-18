from functools import lru_cache
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from researchmate_api.config import Settings
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.services.store import ResearchMateRepository
from researchmate_api.services.evidence_store import EvidenceRepository
from researchmate_api.services.llm import ChatProvider
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.web_search import TavilyWebSearchProvider


bearer = HTTPBearer(auto_error=False)

DEV_USERS: dict[str, tuple[UUID, str, str]] = {
    "dev": (UUID("00000000-0000-4000-8000-000000000001"), "developer", "developer@example.com"),
    "dev-admin": (UUID("00000000-0000-4000-8000-0000000000ad"), "admin", "admin@example.com"),
    "dev-user-a": (UUID("00000000-0000-4000-8000-00000000000a"), "user", "user-a@example.com"),
    "dev-user-b": (UUID("00000000-0000-4000-8000-00000000000b"), "user", "user-b@example.com"),
}


# Resolve the repository from the current application so tests and production adapters share routes.
def get_store(request: Request) -> ResearchMateRepository:
    return request.app.state.store


def get_evidence_store(request: Request) -> EvidenceRepository:
    return request.app.state.evidence_store


def get_chat_provider(request: Request) -> ChatProvider | None:
    return request.app.state.chat_provider


def get_hybrid_store(request: Request) -> QdrantHybridStore | None:
    return request.app.state.hybrid_store


def get_web_search(request: Request) -> TavilyWebSearchProvider | None:
    return request.app.state.web_search


# 生成统一错误 detail，由 FastAPI exception handler 包装成 {"error": ...}。
def error_detail(code: str, message: str, request_id: str = "req_local_dev") -> dict[str, str]:
    return {"code": code, "message": message, "request_id": request_id}


# 保持旧名称兼容历史测试和路由。
def not_implemented_detail(code: str) -> dict[str, str]:
    return error_detail(
        code,
        "This contract is defined, but the requested adapter is not configured for this run.",
    )


# 抛出统一 API 错误。
def raise_api_error(status_code: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status_code, detail=error_detail(code, message))


# 解析本地开发 token；生产环境应替换为 Supabase JWT 校验。
def _development_user(token: str) -> CurrentUser | None:
    if token in DEV_USERS:
        user_id, role, email = DEV_USERS[token]
        return CurrentUser(id=user_id, email=email, role=role)  # type: ignore[arg-type]
    if not token.startswith("dev:"):
        return None
    parts = token.split(":", 3)
    try:
        user_id = UUID(parts[1])
    except (IndexError, ValueError):
        return None
    role = parts[2] if len(parts) > 2 and parts[2] in {"user", "developer", "admin"} else "user"
    email = parts[3] if len(parts) > 3 and parts[3] else None
    return CurrentUser(id=user_id, email=email, role=role)  # type: ignore[arg-type]


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str):
    from jwt import PyJWKClient

    return PyJWKClient(jwks_url, cache_keys=True)


def _supabase_user(token: str, settings: Settings) -> CurrentUser | None:
    from jwt import InvalidTokenError, decode

    jwks_url = settings.jwks_url
    if not jwks_url or not settings.access_token_issuer:
        return None
    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
        claims = decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.access_token_audience,
            issuer=settings.access_token_issuer,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
        user_id = UUID(str(claims["sub"]))
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        return None
    app_metadata = claims.get("app_metadata")
    app_role = app_metadata.get("role") if isinstance(app_metadata, dict) else None
    role = app_role if app_role in {"developer", "admin"} else "user"
    email = claims.get("email") if isinstance(claims.get("email"), str) else None
    return CurrentUser(id=user_id, email=email, role=role)  # type: ignore[arg-type]


def resolve_bearer_token(token: str, settings: Settings) -> CurrentUser | None:
    return (
        _development_user(token)
        if settings.auth_mode == "development"
        else _supabase_user(token, settings)
    )


# Parse only explicit development identities locally; verify signed Supabase JWTs elsewhere.
def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    repository: ResearchMateRepository = Depends(get_store),
) -> CurrentUser:
    if credentials is None:
        raise_api_error(status.HTTP_401_UNAUTHORIZED, "AUTH_REQUIRED", "Bearer token is required.")

    token = credentials.credentials.strip()
    settings: Settings = request.app.state.settings
    user = resolve_bearer_token(token, settings)
    if user is None:
        raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_TOKEN",
            "The bearer token is not valid for the configured authentication mode.",
        )
    repository.ensure_user(user)
    return user


# 校验管理员权限。
def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in {"developer", "admin"}:
        raise_api_error(
            status.HTTP_403_FORBIDDEN,
            "ADMIN_REQUIRED",
            "Developer trace is visible only to developer or admin users.",
        )
    return user
