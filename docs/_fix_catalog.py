fp = r"D:\software\researchMate\apps\api\src\researchmate_api\persistence\evidence_catalog.py"
with open(fp, "r", encoding="utf-8") as f: c = f.read()

pairs = [
    # list_claims: add project status guard
    (
        "where c.project_id = :project_id and c.user_id = :user_id\ngroup by c.id order by c.created_at desc limit 200",
        "where c.project_id = :project_id and c.user_id = :user_id\n  and exists (\n    select 1 from projects p\n    where p.id = c.project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  )\ngroup by c.id order by c.created_at desc limit 200",
    ),
    # list_claim_relations: add project status guard
    (
        "  and source.project_id = :project_id and target.project_id = :project_id\n                    order by r.created_at desc limit 300",
        "  and source.project_id = :project_id and target.project_id = :project_id\n  and exists (\n    select 1 from projects p\n    where p.id = :project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  )\n                    order by r.created_at desc limit 300",
    ),
    # list_reports: add project status guard
    (
        "where r.project_id = :project_id and r.user_id = :user_id\ngroup by r.id order by r.revision desc limit 100",
        "where r.project_id = :project_id and r.user_id = :user_id\n  and exists (\n    select 1 from projects p\n    where p.id = :project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  )\ngroup by r.id order by r.revision desc limit 100",
    ),
    # list_evaluation_datasets: add project status guard (only when project_id is provided)
    (
        "  and (:project_id is null or d.project_id=:project_id)\ngroup by d.id order by d.name,d.version desc",
        "  and (:project_id is null or d.project_id=:project_id)\n  and (:project_id is null or exists (\n    select 1 from projects p\n    where p.id = :project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  ))\ngroup by d.id order by d.name,d.version desc",
    ),
]

miss = 0
for i, (old, new) in enumerate(pairs, 1):
    if old not in c:
        print(f"MISS {i}: {old[:60]}")
        miss += 1
    c = c.replace(old, new, 1)

with open(fp, "w", encoding="utf-8") as f: f.write(c)
print(f"Done. {miss} misses.")