fp = r"D:\software\researchMate\apps\api\src\researchmate_api\persistence\evidence_catalog.py"
with open(fp, "r", encoding="utf-8") as f: c = f.read()

def insert_after(text, anchor, insertion):
    idx = text.find(anchor)
    if idx < 0:
        print(f"MISS: {anchor[:50]}")
        return text
    end = idx + len(anchor)
    return text[:end] + insertion + text[end:]

# list_claims: insert after WHERE clause
c = insert_after(c,
    "where c.project_id = :project_id and c.user_id = :user_id",
    "\n  and exists (\n    select 1 from projects p\n    where p.id = c.project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  )",
)

# list_reports: insert after WHERE clause
c = insert_after(c,
    "where r.project_id = :project_id and r.user_id = :user_id",
    "\n  and exists (\n    select 1 from projects p\n    where p.id = :project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  )",
)

# list_evaluation_datasets: insert after project_id filter
c = insert_after(c,
    "and (:project_id is null or d.project_id=:project_id)",
    "\n  and (:project_id is null or exists (\n    select 1 from projects p\n    where p.id = :project_id and p.user_id = :user_id\n      and p.status = 'active' and p.deleted_at is null\n  ))",
)

with open(fp, "w", encoding="utf-8") as f: f.write(c)

# Verify
with open(fp, "r", encoding="utf-8") as f: c2 = f.read()
count = c2.count("exists")
print(f"exists count: {count}")