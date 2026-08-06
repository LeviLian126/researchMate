fp = r"D:\software\researchMate\apps\api\src\researchmate_api\persistence\evidence_catalog.py"
with open(fp, "r", encoding="utf-8") as f: c = f.read()

guard = "\n  and exists (\n    select 1 from projects p\n    where p.id = {proj_ref} and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  )"

# list_claims
c = c.replace(
    "where c.project_id = :project_id and c.user_id = :user_id\ngroup by c.id",
    "where c.project_id = :project_id and c.user_id = :user_id" + guard.format(proj_ref="c.project_id") + "\ngroup by c.id",
    1,
)

# list_reports
c = c.replace(
    "where r.project_id = :project_id and r.user_id = :user_id\ngroup by r.id",
    "where r.project_id = :project_id and r.user_id = :user_id" + guard.format(proj_ref=":project_id") + "\ngroup by r.id",
    1,
)

# list_evaluation_datasets
c = c.replace(
    "and (:project_id is null or d.project_id=:project_id)\ngroup by d.id",
    "and (:project_id is null or d.project_id=:project_id)\n  and (:project_id is null or exists (\n    select 1 from projects p\n    where p.id = :project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  ))\ngroup by d.id",
    1,
)

with open(fp, "w", encoding="utf-8") as f: f.write(c)

# Verify
with open(fp, "r", encoding="utf-8") as f: c2 = f.read()
count = c2.count("exists")
print(f"exists count: {count}")