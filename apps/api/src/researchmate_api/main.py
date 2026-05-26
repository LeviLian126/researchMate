from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from researchmate_api.routers import ask, dev_traces, documents, health, jobs, me, projects, quiz, runs


# 创建 FastAPI 应用并注册业务路由。
def create_app() -> FastAPI:
    app = FastAPI(
        title="ResearchMate API",
        version="0.1.0",
        description="Local-first ResearchMate API with swappable cloud/provider adapters.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
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
    return app


# 将 HTTPException 转成统一错误体，避免泄露 stack trace。
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and {"code", "message", "request_id"} <= set(exc.detail):
        payload = exc.detail
    else:
        payload = {
            "code": "HTTP_ERROR",
            "message": str(exc.detail),
            "request_id": "req_local_dev",
        }
    return JSONResponse(status_code=exc.status_code, content={"error": payload})


# 将请求校验错误转成统一错误体，只暴露字段路径和错误类型。
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
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
                "request_id": "req_validation",
            }
        },
    )


app = create_app()
