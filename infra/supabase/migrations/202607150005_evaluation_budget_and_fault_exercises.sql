-- Fail-closed evaluation budgets and auditable, non-destructive reliability simulations.

alter table evaluation_runs
  add column if not exists budget_limit_usd numeric(12,6)
    check (budget_limit_usd is null or budget_limit_usd > 0),
  add column if not exists budget_reserved_usd numeric(12,6) not null default 0
    check (budget_reserved_usd >= 0),
  add column if not exists last_error_code text;

update evaluation_runs
set budget_limit_usd = nullif(summary ->> 'max_cost_usd', '')::numeric
where budget_limit_usd is null
  and summary ->> 'max_cost_usd' is not null;

-- Historical pending rows created before budget enforcement receive the same
-- conservative default as new API requests; no runnable evaluation is unlimited.
update evaluation_runs set budget_limit_usd = 1.000000
where budget_limit_usd is null;

alter table evaluation_runs
  alter column budget_limit_usd set default 1.000000,
  alter column budget_limit_usd set not null;

alter table evaluation_runs
  add constraint evaluation_runs_budget_within_limit
  check (budget_limit_usd is null or budget_reserved_usd <= budget_limit_usd)
  not valid;

alter table evaluation_runs validate constraint evaluation_runs_budget_within_limit;

create table if not exists fault_exercises (
  id uuid primary key,
  requested_by uuid not null references profiles(id) on delete cascade,
  target_run_id uuid references workflow_runs(id) on delete set null,
  scenario text not null
    check (scenario in ('llm_timeout', 'qdrant_unavailable', 'worker_interrupt', 'r2_failure')),
  duration_seconds integer not null check (duration_seconds between 1 and 60),
  status text not null default 'pending'
    check (status in ('pending', 'running', 'succeeded', 'failed')),
  request_hash text not null,
  idempotency_key text not null,
  attempts integer not null default 0 check (attempts >= 0),
  lease_owner text,
  lease_expires_at timestamptz,
  expires_at timestamptz not null,
  safe_result jsonb not null default '{}'::jsonb,
  last_error_code text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (requested_by, idempotency_key)
);

create index if not exists idx_fault_exercises_dispatch
  on fault_exercises(status, lease_expires_at, created_at);
create index if not exists idx_fault_exercises_target
  on fault_exercises(target_run_id, created_at desc);

alter table fault_exercises enable row level security;

create policy fault_exercises_owner_select on fault_exercises
  for select using (requested_by = auth.uid());
create policy fault_exercises_owner_insert on fault_exercises
  for insert with check (requested_by = auth.uid());
