"""Create LangGraph-owned checkpoint tables during an approved schema phase.

Manually invoked during the protected release migration phase (NOT called by
render.yaml, the Dockerfile, or CI). Documented in docs/learn/infra.html as
script #8. Requires ALLOW_SCHEMA_APPLY=1 as a guard against accidental runs.
LangGraph owns and versions its checkpoint DDL; this must never run
concurrently inside task delivery.
"""

from __future__ import annotations

import os


def main() -> None:
    """Run protected LangGraph checkpoint setup against the configured database."""
    if os.getenv("ALLOW_SCHEMA_APPLY") != "1":
        raise SystemExit("Set ALLOW_SCHEMA_APPLY=1 for an explicitly approved schema apply")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    from langgraph.checkpoint.postgres import PostgresSaver

    checkpoint_url = database_url.replace("postgresql+psycopg://", "postgresql://")
    with PostgresSaver.from_conn_string(checkpoint_url) as checkpointer:
        # LangGraph owns its checkpoint DDL; see module docstring for run constraints.
        checkpointer.setup()


if __name__ == "__main__":
    main()
