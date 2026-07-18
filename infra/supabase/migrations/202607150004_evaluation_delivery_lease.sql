-- Resumable evaluation-run ownership for bounded parallel case execution.
alter table evaluation_runs
  add column if not exists attempts integer not null default 0 check (attempts >= 0),
  add column if not exists lease_owner text,
  add column if not exists lease_expires_at timestamptz;

create index if not exists idx_evaluation_runs_dispatch_lease
  on evaluation_runs(status, lease_expires_at, created_at);
