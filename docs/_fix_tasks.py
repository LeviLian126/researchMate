fp = r"D:\software\researchMate\workers\ai-worker\src\researchmate_worker\tasks.py"
with open(fp, "r", encoding="utf-8") as f: c = f.read()

# RM-QA2-006: Add catch-all to ingest_document (first occurrence of the pattern)
old1 = """    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise


@celery_app.task(bind=True, name="researchmate.delete_document", max_retries=5)"""
new1 = """    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise
    except Exception:
        _mark_job_bootstrap_failed(settings, payload.job_id, "INGESTION_INTERNAL_ERROR")
        raise


@celery_app.task(bind=True, name="researchmate.delete_document", max_retries=5)"""

# RM-QA2-006: Add catch-all to delete_document
old2 = """    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise


@celery_app.task(bind=True, name="researchmate.delete_project", max_retries=8)"""
new2 = """    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise
    except Exception:
        _mark_job_bootstrap_failed(settings, payload.job_id, "DELETION_INTERNAL_ERROR")
        raise


@celery_app.task(bind=True, name="researchmate.delete_project", max_retries=8)"""

# RM-QA2-006: Add catch-all to delete_project (followed by run_workflow)
old3 = """    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise


@celery_app.task(bind=True, name="researchmate.run_workflow", max_retries=5)"""
new3 = """    except IngestionFailure as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(exc=IngestionFailure(exc.code, retryable=True), countdown=countdown)
        raise
    except Exception:
        _mark_job_bootstrap_failed(settings, payload.job_id, "PROJECT_DELETION_INTERNAL_ERROR")
        raise


@celery_app.task(bind=True, name="researchmate.run_workflow", max_retries=5)"""

# RM-QA2-006: Add catch-all to run_evaluation
old4 = """    except EvaluationRuntimeError as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(
                exc=EvaluationRuntimeError(exc.code, retryable=True),
                countdown=countdown,
            )
        raise"""
new4 = """    except EvaluationRuntimeError as exc:
        if exc.retryable:
            countdown = min(300, 2 ** min(int(self.request.retries) + 1, 8))
            raise self.retry(
                exc=EvaluationRuntimeError(exc.code, retryable=True),
                countdown=countdown,
            )
        raise
    except Exception:
        _mark_evaluation_run_failed(None, payload.evaluation_run_id, "EVALUATION_INTERNAL_ERROR")
        raise"""

# RM-QA2-002: Add try/except to run_fault_simulation
old5 = """    payload = FaultSimulationTaskEvent.model_validate(event)
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    return build_fault_simulation_service(WorkerSettings()).run(
        payload.exercise_id,
        worker_id=worker_id,
    )"""
new5 = """    payload = FaultSimulationTaskEvent.model_validate(event)
    try:
        settings = WorkerSettings()
    except Exception:
        _mark_fault_exercise_failed(None, payload.exercise_id, "WORKER_CONFIG_INVALID")
        raise
    worker_id = str(getattr(self.request, "hostname", None) or self.request.id or "worker")
    try:
        return build_fault_simulation_service(settings).run(
            payload.exercise_id,
            worker_id=worker_id,
        )
    except Exception:
        _mark_fault_exercise_failed(settings, payload.exercise_id, "FAULT_SIMULATION_INTERNAL_ERROR")
        raise"""

miss = 0
for i, (old, new) in enumerate([(old1, new1), (old2, new2), (old3, new3), (old4, new4), (old5, new5)], 1):
    if old not in c:
        print(f"MISS {i}: {old[:60]}")
        miss += 1
    c = c.replace(old, new, 1)

with open(fp, "w", encoding="utf-8") as f: f.write(c)
print(f"Done. {miss} misses.")