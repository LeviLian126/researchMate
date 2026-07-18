from __future__ import annotations

import json
import socket
from typing import Any

from sqlalchemy import Engine, text


def record_heartbeat(
    engine: Engine,
    component: str,
    *,
    instance_id: str | None = None,
    status: str = "ready",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Upsert a non-secret liveness signal consumed by the public readiness probe."""

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into runtime_heartbeats(component,instance_id,status,safe_metadata,updated_at)
                values (:component,:instance_id,:status,cast(:metadata as jsonb),now())
                on conflict (component) do update set
                  instance_id=excluded.instance_id,status=excluded.status,
                  safe_metadata=excluded.safe_metadata,updated_at=excluded.updated_at
                """
            ),
            {
                "component": component,
                "instance_id": instance_id or socket.gethostname(),
                "status": status,
                "metadata": json.dumps(metadata or {}, separators=(",", ":")),
            },
        )
