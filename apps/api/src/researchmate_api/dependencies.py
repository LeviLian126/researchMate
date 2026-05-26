from uuid import UUID, uuid5, NAMESPACE_URL

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.services.store import store


bearer = HTTPBearer(auto_error=False)

DEV_USERS: dict[str, tuple[UUID, str, str]] = {
    "dev": (UUID("00000000-0000-4000-8000-000000000001"), "developer", "developer@example.com"),
    "dev-admin": (UUID("00000000-0000-4000-8000-0000000000ad"), "admin", "admin@example.com"),
    "dev-user-a": (UUID("00000000-0000-4000-8000-00000000000a"), "user", "user-a@example.com"),
    "dev-user-b": (UUID("00000000-0000-4000-8000-00000000000b"), "user", "user-b@example.com"),
}


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
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentUser:
    if credentials is None:
        raise_api_error(status.HTTP_401_UNAUTHORIZED, "AUTH_REQUIRED", "Bearer token is required.")

    token = credentials.credentials.strip()
    if token in DEV_USERS:
        user_id, role, email = DEV_USERS[token]
        user = CurrentUser(id=user_id, email=email, role=role)  # type: ignore[arg-type]
        store.ensure_user(user)
        return user

    if token.startswith("dev:"):
        parts = token.split(":", 3)
        try:
            user_id = UUID(parts[1])
        except (IndexError, ValueError):
            user_id = uuid5(NAMESPACE_URL, token)
        role = parts[2] if len(parts) > 2 and parts[2] in {"user", "developer", "admin"} else "user"
        email = parts[3] if len(parts) > 3 else None
        user = CurrentUser(id=user_id, email=email, role=role)  # type: ignore[arg-type]
        store.ensure_user(user)
        return user

    user = CurrentUser(id=uuid5(NAMESPACE_URL, token), email=None, role="user")
    store.ensure_user(user)
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
