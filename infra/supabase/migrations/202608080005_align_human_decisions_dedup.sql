-- BE-7: Align human_decisions dedup with the public Idempotency-Key contract.
--
-- The header Idempotency-Key is the documented dedup contract for the human-decision
-- endpoint. The InMemory adapter keys dedup on (run_id, idempotency_key); the initial
-- schema instead created unique (run_id, interrupt_key), which let repeated retries
-- with the same header but a different body silently bypass the dedup the caller
-- expected when the workflow re-issued a slightly different interrupt_key for the
-- same review node. Add idempotency_key to the table, backfill historical rows from
-- the existing interrupt_key, swap the unique constraint accordingly, and keep
-- interrupt_key as a non-unique reference to the run_events interrupt being resolved.

alter table human_decisions
  add column if not exists idempotency_key text;

update human_decisions
set idempotency_key = interrupt_key
where idempotency_key is null;

alter table human_decisions
  alter column idempotency_key set not null;

alter table human_decisions
  drop constraint if exists human_decisions_run_id_interrupt_key_key;
alter table human_decisions
  drop constraint if exists human_decisions_run_id_idempotency_key_key;
alter table human_decisions
  add constraint human_decisions_run_id_idempotency_key_key
  unique (run_id, idempotency_key);

create index if not exists idx_human_decisions_run_interrupt
  on human_decisions(run_id, interrupt_key);

-- Rollback:
--   drop index if exists idx_human_decisions_run_interrupt;
--   alter table human_decisions drop constraint if exists human_decisions_run_id_idempotency_key_key;
--   alter table human_decisions add constraint human_decisions_run_id_interrupt_key_key unique (run_id, interrupt_key);
--   alter table human_decisions drop column if exists idempotency_key;
