-- Operational readiness, workflow delivery leases, and fail-closed research budgets.
-- These fields are additive so an existing development database can be upgraded safely.

alter table workflow_runs
  add column if not exists delivery_attempts integer not null default 0 check (delivery_attempts >= 0),
  add column if not exists lease_owner text,
  add column if not exists lease_expires_at timestamptz,
  add column if not exists budget_limit_usd numeric(12,6) not null default 1.000000
    check (budget_limit_usd > 0 and budget_limit_usd <= 25),
  add column if not exists budget_reserved_usd numeric(12,6) not null default 0
    check (budget_reserved_usd >= 0),
  add column if not exists actual_cost_usd numeric(12,6) not null default 0
    check (actual_cost_usd >= 0),
  add constraint workflow_runs_budget_within_limit
    check (budget_reserved_usd <= budget_limit_usd);

create index if not exists idx_workflow_runs_delivery_lease
  on workflow_runs(status, lease_expires_at, created_at);

create table if not exists runtime_heartbeats (
  component text primary key check (component in ('worker', 'dispatcher')),
  instance_id text not null,
  status text not null check (status in ('ready', 'degraded', 'stopping')),
  safe_metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table runtime_heartbeats enable row level security;

-- Runtime heartbeats are backend-only operational state. No browser policy is created;
-- the API and workers use the server database role and /readyz exposes only safe status.
revoke all on runtime_heartbeats from anon, authenticated;

-- Accepted pipeline configurations are immutable, non-secret executable catalog entries.
-- Demo users may discover them; draft/candidate versions remain creator/admin-only.
drop policy if exists pipeline_versions_referenced_select on pipeline_versions;
create policy pipeline_versions_referenced_select on pipeline_versions
  for select using (
    status = 'accepted'
    or created_by = auth.uid()
    or exists (
      select 1 from workflow_runs
      where workflow_runs.pipeline_version_id = pipeline_versions.id
        and workflow_runs.user_id = auth.uid()
    )
    or exists (
      select 1 from profiles
      where profiles.id = auth.uid()
        and profiles.role in ('developer', 'admin')
    )
  );
