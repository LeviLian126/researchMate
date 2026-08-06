fp = r"D:\software\researchMate\apps\api\src\researchmate_api\persistence\evidence_catalog.py"
with open(fp, "r", encoding="utf-8") as f: c = f.read()

import re

# list_claims: add project status guard after the WHERE clause
c = c.replace(
    "where c.project_id = :project_id and c.user_id = :user_id\ngroup by c.id",
    "where c.project_id = :project_id and c.user_id = :user_id\n  and exists (\n    select 1 from projects p\n    where p.id = c.project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  )\ngroup by c.id",
    1,
)

# list_reports: add project status guard after the WHERE clause
c = c.replace(
    "where r.project_id = :project_id and r.user_id = :user_id\ngroup by r.id",
    "where r.project_id = :project_id and r.user_id = :user_id\n  and exists (\n    select 1 from projects p\n    where p.id = :project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  )\ngroup by r.id",
    1,
)

# list_evaluation_datasets: add project status guard after the project_id filter
c = c.replace(
    "and (:project_id is null or d.project_id=:project_id)\ngroup by d.id",
    "and (:project_id is null or d.project_id=:project_id)\n  and (:project_id is null or exists (\n    select 1 from projects p\n    where p.id = :project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  ))\ngroup by d.id",
    1,
)

# Verify list_claim_relations was already fixed
if "and source.project_id = :project_id and target.project_id = :project_id\n                    order by" in c:
    print("list_claim_relations still needs fix")
else:
    print("list_claim_relations already fixed or different pattern")

with open(fp, "w", encoding="utf-8") as f: f.write(c)
print("Done.")