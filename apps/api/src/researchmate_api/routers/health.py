from fastapi import APIRouter


router = APIRouter()


# 返回服务健康状态。
@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

