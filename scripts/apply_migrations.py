from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "infra" / "supabase" / "migrations"
LOCK_KEY = 726_334_129


def migration_files() -> list[Path]:
    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        raise SystemExit("No SQL migrations were found")
    if len({path.name.split("_", 1)[0] for path in files}) != len(files):
        raise SystemExit("Migration version prefixes must be unique")
    return files


def validate_files() -> None:
    for path in migration_files():
        source = path.read_text(encoding="utf-8").strip()
        if not source:
            raise SystemExit(f"Migration is empty: {path.name}")
        if "drop database" in source.lower():
            raise SystemExit(f"Destructive database operation is not allowed: {path.name}")


def apply(database_url: str) -> None:
    if os.getenv("ALLOW_SCHEMA_APPLY") != "1":
        raise SystemExit("Set ALLOW_SCHEMA_APPLY=1 for an explicitly approved schema apply")
    import psycopg

    with psycopg.connect(database_url, autocommit=False) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select pg_advisory_xact_lock(%s)", (LOCK_KEY,))
            cursor.execute(
                """
                create table if not exists researchmate_schema_migrations (
                  version text primary key,
                  checksum_sha256 text not null,
                  applied_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                "select version,checksum_sha256 from researchmate_schema_migrations"
            )
            applied = dict(cursor.fetchall())
            for path in migration_files():
                source = path.read_text(encoding="utf-8")
                digest = sha256(source.encode("utf-8")).hexdigest()
                previous = applied.get(path.name)
                if previous is not None:
                    if previous != digest:
                        raise RuntimeError(f"Applied migration checksum changed: {path.name}")
                    continue
                cursor.execute(source)
                cursor.execute(
                    """
                    insert into researchmate_schema_migrations(version,checksum_sha256)
                    values (%s,%s)
                    """,
                    (path.name, digest),
                )
        connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="ResearchMate additive migration runner")
    parser.add_argument("--check-files", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    validate_files()
    if args.apply:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise SystemExit("DATABASE_URL is required")
        apply(database_url)
    elif not args.check_files:
        parser.error("choose --check-files or --apply")


if __name__ == "__main__":
    main()
