from __future__ import annotations

import os


def main() -> None:
    if os.getenv("ALLOW_SCHEMA_APPLY") != "1":
        raise SystemExit("Set ALLOW_SCHEMA_APPLY=1 for an explicitly approved schema apply")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    from langgraph.checkpoint.postgres import PostgresSaver

    checkpoint_url = database_url.replace("postgresql+psycopg://", "postgresql://")
    with PostgresSaver.from_conn_string(checkpoint_url) as checkpointer:
        # LangGraph owns and versions its checkpoint DDL. Run this only during the
        # protected release migration phase, never concurrently inside task delivery.
        checkpointer.setup()


if __name__ == "__main__":
    main()
