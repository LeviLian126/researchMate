from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text


router = APIRouter()


# 返回服务健康状态。
@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request) -> JSONResponse:
    """Probe non-charging dependencies required to safely accept production work."""

    settings = request.app.state.settings
    components: dict[str, Any] = {
        "database": "not_required",
        "redis": "not_required",
        "worker": "not_required",
        "dispatcher": "not_required",
        "outbox": "not_required",
        "checkpoint": "not_required",
        "qdrant": "not_required",
        "object_storage": "not_required",
        "llm": "not_required",
        "web_search": "not_required",
    }
    failures: list[str] = []
    if settings.repository_backend == "postgres":
        engine = getattr(request.app.state.store, "engine", None)
        if engine is None:
            components["database"] = "unavailable"
            failures.append("database")
        else:
            try:
                with engine.connect() as connection:
                    connection.execute(text("select 1"))
                    checkpoint_tables = connection.execute(
                        text(
                            """
                            select count(*) from unnest(array[
                              'checkpoint_migrations','checkpoints',
                              'checkpoint_blobs','checkpoint_writes'
                            ]) as req(name)
                            where to_regclass('public.' || req.name) is not null
                            """
                        )
                    ).scalar_one()
                    components["checkpoint"] = (
                        "ready" if int(checkpoint_tables) == 4 else "unavailable"
                    )
                    if int(checkpoint_tables) != 4:
                        failures.append("checkpoint")
                    heartbeat_rows = connection.execute(
                        text(
                            """
                            select component,status,
                              updated_at >= now() - make_interval(secs => :max_age) as fresh
                            from runtime_heartbeats
                            where component in ('worker','dispatcher')
                            """
                        ),
                        {"max_age": settings.runtime_heartbeat_max_age_seconds},
                    ).mappings().all()
                    heartbeats = {row["component"]: row for row in heartbeat_rows}
                    for component in ("worker", "dispatcher"):
                        heartbeat = heartbeats.get(component)
                        ready = bool(
                            heartbeat
                            and heartbeat["status"] == "ready"
                            and heartbeat["fresh"]
                        )
                        components[component] = "ready" if ready else "unavailable"
                        if not ready:
                            failures.append(component)
                    outbox = connection.execute(
                        text(
                            """
                            select
                              count(*) filter (
                                where status in ('pending','publishing','failed')
                                  and created_at < now() - make_interval(secs => :max_age)
                              ) as stale_count,
                              count(*) filter (
                                where status='failed' and attempts >= :max_attempts
                              ) as exhausted_count
                            from outbox_events
                            """
                        ),
                        {
                            "max_age": settings.outbox_pending_max_age_seconds,
                            "max_attempts": 8,
                        },
                    ).mappings().one()
                    outbox_ready = not int(outbox["stale_count"]) and not int(
                        outbox["exhausted_count"]
                    )
                    components["outbox"] = "ready" if outbox_ready else "backlogged"
                    if not outbox_ready:
                        failures.append("outbox")
                components["database"] = "ready"
            except Exception:
                components["database"] = "unavailable"
                failures.append("database")
                for component in ("worker", "dispatcher", "outbox", "checkpoint"):
                    components[component] = "unavailable"
                    if component not in failures:
                        failures.append(component)
    if settings.redis_url:
        try:
            from redis import Redis

            client = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
            client.ping()
            client.close()
            components["redis"] = "ready"
        except Exception:
            components["redis"] = "unavailable"
            failures.append("redis")
    elif settings.app_env in {"preview", "production"}:
        components["redis"] = "unavailable"
        failures.append("redis")
    if settings.qdrant_url:
        hybrid = request.app.state.hybrid_store
        try:
            hybrid.client.get_collection(hybrid.collection)
            components["qdrant"] = "ready"
        except Exception:
            components["qdrant"] = "unavailable"
            failures.append("qdrant")
    if settings.object_storage_configured:
        components["object_storage"] = "configured_not_probed"
    elif settings.app_env in {"preview", "production"}:
        components["object_storage"] = "unavailable"
        failures.append("object_storage")
    if request.app.state.chat_provider is not None:
        components["llm"] = "configured_not_charged"
    elif settings.app_env in {"preview", "production"}:
        components["llm"] = "unavailable"
        failures.append("llm")
    if request.app.state.web_search is not None:
        components["web_search"] = "configured_not_charged"
    elif settings.app_env in {"preview", "production"}:
        components["web_search"] = "unavailable"
        failures.append("web_search")
    payload = {
        "status": "ready" if not failures else "not_ready",
        "environment": settings.app_env,
        "components": components,
        "failed_components": failures,
    }
    return JSONResponse(status_code=200 if not failures else 503, content=payload)
