from fastapi import FastAPI

from researchmate_api.routers import ask, dev_traces, documents, health, jobs, me, projects, quiz, runs


# 创建 FastAPI 应用并注册契约路由。
def create_app() -> FastAPI:
    app = FastAPI(
        title="ResearchMate API",
        version="0.1.0",
        description="Contract-first API shell for ResearchMate MVP.",
    )
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


app = create_app()

