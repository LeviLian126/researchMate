-- Runtime delivery metadata required for safe at-least-once Celery execution.
alter table jobs
  add column if not exists attempts integer not null default 0 check (attempts >= 0),
  add column if not exists lease_owner text,
  add column if not exists lease_expires_at timestamptz,
  add column if not exists started_at timestamptz,
  add column if not exists completed_at timestamptz;

create index if not exists idx_jobs_dispatch_lease
  on jobs(status, lease_expires_at, updated_at);
