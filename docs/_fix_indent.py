import re

# 1. Fix mcp_server.py - the except blocks have 7 spaces instead of 8
fp = r"D:\software\researchMate\apps\api\src\researchmate_api\mcp_server.py"
with open(fp, "r", encoding="utf-8") as f: c = f.read()
# The problem: lines with 7-space indent that should be 8
c = c.replace("       except IdempotencyError as exc:\n           raise ValueError(exc.code) from exc\n       except (ValueError, GroundedQueryError) as exc:\n           if \"coordinator\" in locals():\n               coordinator.abandon()\n           raise ValueError(getattr(exc, \"code\", \"INVALID_REQUEST\")) from exc\n        except Exception:\n            if \"coordinator\" in locals():\n                coordinator.abandon()\n            raise\n       return response.model_dump(mode=\"json\")",
              "        except IdempotencyError as exc:\n            raise ValueError(exc.code) from exc\n        except (ValueError, GroundedQueryError) as exc:\n            if \"coordinator\" in locals():\n                coordinator.abandon()\n            raise ValueError(getattr(exc, \"code\", \"INVALID_REQUEST\")) from exc\n        except Exception:\n            if \"coordinator\" in locals():\n                coordinator.abandon()\n            raise\n        return response.model_dump(mode=\"json\")")
with open(fp, "w", encoding="utf-8") as f: f.write(c)
print("mcp_server.py fixed")

# 2. Fix evidence_store.py - fingerprint line has 11 spaces instead of 12
fp = r"D:\software\researchMate\apps\api\src\researchmate_api\services\evidence_store.py"
with open(fp, "r", encoding="utf-8") as f: c = f.read()
c = c.replace("            key = (run_id, idempotency_key)\n           fingerprint = evidence_fingerprint(payload)\n           existing = self.decisions.get(key)",
              "            key = (run_id, idempotency_key)\n            fingerprint = evidence_fingerprint(payload)\n            existing = self.decisions.get(key)")
with open(fp, "w", encoding="utf-8") as f: f.write(c)
print("evidence_store.py fixed")

# 3. Fix evidence_runs.py - with/lock_idempotency/run lines have wrong indent
fp = r"D:\software\researchMate\apps\api\src\researchmate_api\persistence\evidence_runs.py"
with open(fp, "r", encoding="utf-8") as f: c = f.read()
c = c.replace("       with self._transaction(user) as connection:\n            self._lock_idempotency(connection, user.id, idempotency_key)\n           run = connection.execute(",
              "        with self._transaction(user) as connection:\n            self._lock_idempotency(connection, user.id, idempotency_key)\n            run = connection.execute(")
with open(fp, "w", encoding="utf-8") as f: f.write(c)
print("evidence_runs.py fixed")

# 4. Fix _postgres_memory.py - def/docstring have 3/7 spaces instead of 4/8
fp = r"D:\software\researchMate\apps\api\src\researchmate_api\persistence\_postgres_memory.py"
with open(fp, "r", encoding="utf-8") as f: c = f.read()
c = c.replace("   def get_runtime_rerank_config(self) -> RuntimeRerankConfig:\n       \"\"\"Return the active runtime rerank configuration.\"\"\"\n        with self._transaction() as connection:",
              "    def get_runtime_rerank_config(self) -> RuntimeRerankConfig:\n        \"\"\"Return the active runtime rerank configuration.\"\"\"\n        with self._transaction() as connection:")
with open(fp, "w", encoding="utf-8") as f: f.write(c)
print("_postgres_memory.py fixed")