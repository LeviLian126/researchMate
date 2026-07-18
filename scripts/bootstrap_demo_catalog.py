from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from uuid import UUID, uuid4


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Idempotently create an accepted pipeline and frozen evaluation dataset"
    )
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--project-id", required=True, type=UUID)
    parser.add_argument("--case-limit", type=int, default=10)
    args = parser.parse_args()
    if os.getenv("ALLOW_DEMO_BOOTSTRAP") != "1":
        raise SystemExit("Set ALLOW_DEMO_BOOTSTRAP=1 after reviewing the target user/project")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    if not 1 <= args.case_limit <= 50:
        raise SystemExit("--case-limit must be between 1 and 50")

    import psycopg
    from psycopg.types.json import Jsonb

    configuration = {
        "retrieval_limit": 12,
        "model": os.getenv("NVIDIA_MODEL", "z-ai/glm-5.2"),
        "evidence_prompt_version": "evidence-review-v1",
        "evaluation_prompt_version": "grounded-answer-v1",
        "retrieval_mode": "dense_sparse_rerank",
    }
    prompt_hash = sha256(b"grounded-answer-v1").hexdigest()
    code_sha = os.getenv("GITHUB_SHA", "local-uncommitted")
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select pg_advisory_xact_lock(hashtextextended(%s,2))", (str(args.user_id),))
            cursor.execute(
                """
                select 1 from projects p join profiles u on u.id=p.user_id
                where p.id=%s and p.user_id=%s and p.deleted_at is null
                  and u.role in ('developer','admin')
                """,
                (args.project_id, args.user_id),
            )
            if cursor.fetchone() is None:
                raise SystemExit(
                    "The project is missing, foreign, or its owner is not a developer/admin"
                )
            pipeline_name = f"researchmate-evidence-{str(args.user_id)[:8]}"
            cursor.execute(
                """
                insert into pipeline_versions(
                  id,name,version,status,configuration,prompt_hash,code_sha,created_by,accepted_at
                ) values (%s,%s,1,'accepted',%s,%s,%s,%s,now())
                on conflict(name,version) do update set
                  status='accepted',configuration=excluded.configuration,
                  prompt_hash=excluded.prompt_hash,code_sha=excluded.code_sha,
                  accepted_at=now()
                returning id
                """,
                (uuid4(), pipeline_name, Jsonb(configuration), prompt_hash, code_sha, args.user_id),
            )
            pipeline_id = cursor.fetchone()[0]
            cursor.execute(
                """
                insert into evaluation_datasets(
                  id,user_id,project_id,name,version,status,description
                ) values (%s,%s,%s,'portfolio-regression',1,'draft',
                  'Deterministic evidence-grounding cases bootstrapped from ready project chunks.')
                on conflict(user_id,name,version) do update set project_id=excluded.project_id
                returning id
                """,
                (uuid4(), args.user_id, args.project_id),
            )
            dataset_id = cursor.fetchone()[0]
            cursor.execute(
                """
                select c.id,c.source_title,left(c.text,500)
                from chunks c join documents d on d.id=c.document_id
                where c.user_id=%s and c.project_id=%s and d.status='ready'
                  and d.deleted_at is null
                order by c.created_at,c.id limit %s
                """,
                (args.user_id, args.project_id, args.case_limit),
            )
            rows = cursor.fetchall()
            if not rows:
                raise SystemExit("Ingest at least one ready document before bootstrapping the catalog")
            for index, (chunk_id, source_title, excerpt) in enumerate(rows, start=1):
                case_key = f"bootstrap-{index:03d}-{str(chunk_id)[:8]}"
                cursor.execute(
                    """
                    insert into evaluation_cases(
                      id,dataset_id,case_key,input,expected_output,expected_evidence
                    ) values (%s,%s,%s,%s,null,%s)
                    on conflict(dataset_id,case_key) do update set
                      input=excluded.input,expected_evidence=excluded.expected_evidence
                    """,
                    (
                        uuid4(),
                        dataset_id,
                        case_key,
                        Jsonb(
                            {
                                "question": f"What evidence is presented in {source_title}?",
                                "reference_excerpt": excerpt,
                            }
                        ),
                        Jsonb({"chunk_ids": [str(chunk_id)]}),
                    ),
                )
            cursor.execute(
                "update evaluation_datasets set status='frozen' where id=%s",
                (dataset_id,),
            )
        connection.commit()
    print(
        json.dumps(
            {"pipeline_version_id": str(pipeline_id), "dataset_id": str(dataset_id)},
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
