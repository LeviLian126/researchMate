from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from researchmate_api.schemas.common import CurrentUser


bearer = HTTPBearer(auto_error=False)


# 生成统一的未实现错误，避免泄露内部细节。
def not_implemented_detail(code: str) -> dict[str, str]:
    return {
        "code": code,
        "message": "This contract is defined, but business logic is not implemented yet.",
        "request_id": "req_contract_scaffold",
    }


# 解析当前用户，后续替换为 Supabase JWT 校验。
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=not_implemented_detail("AUTH_REQUIRED"),
        )
    return CurrentUser(
        id=UUID("00000000-0000-4000-8000-000000000001"),
        email="developer@example.com",
        role="developer",
    )


# 校验管理员权限，后续接入 profiles.role 或 allowlist。
def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in {"developer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=not_implemented_detail("ADMIN_REQUIRED"),
        )
    return user

