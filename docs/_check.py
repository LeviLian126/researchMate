fp = r"D:\software\researchMate\apps\api\src\researchmate_api\persistence\evidence_catalog.py"
with open(fp, "r", encoding="utf-8") as f: c = f.read()

# Check line ending style
if "\r\n" in c:
    print("File uses CRLF")
    nl = "\r\n"
else:
    print("File uses LF")
    nl = "\n"

# Check what is actually after the WHERE clauses
for pattern in [
    "where c.project_id = :project_id and c.user_id = :user_id",
    "where r.project_id = :project_id and r.user_id = :user_id",
    "and (:project_id is null or d.project_id=:project_id)",
]:
    idx = c.find(pattern)
    if idx >= 0:
        after = c[idx + len(pattern):idx + len(pattern) + 80]
        print(f"Found at {idx}, after: {repr(after[:60])}")
    else:
        print(f"Not found: {pattern[:50]}")