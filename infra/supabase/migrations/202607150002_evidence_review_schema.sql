-- Additive evidence-review, orchestration, outbox, and evaluation schema.
-- This migration intentionally keeps PostgreSQL as the source of truth; R2,
-- Qdrant, and Redis remain external projections or coordination services.

create table if not exists pipeline_versions (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  version integer not null check (version > 0),
  status text not null default 'draft'
    check (status in ('draft', 'candidate', 'accepted', 'retired')),
  configuration jsonb not null,
  prompt_hash text not null,
  code_sha text not null,
  created_by uuid not null references profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  accepted_at timestamptz,
  unique (name, version)
);

create table if not exists workflow_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  conversation_id uuid references conversations(id) on delete set null,
  pipeline_version_id uuid not null references pipeline_versions(id) on delete restrict,
  kind text not null check (kind in ('ask', 'evidence_review', 'report_refresh')),
  status text not null default 'pending'
    check (status in ('pending', 'running', 'waiting_human', 'succeeded', 'failed', 'cancelled')),
  idempotency_key text not null,
  checkpoint_ref text,
  input jsonb not null,
  output jsonb,
  error_code text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  unique (user_id, idempotency_key)
);

create table if not exists run_events (
  id bigint generated always as identity primary key,
  run_id uuid not null references workflow_runs(id) on delete cascade,
  sequence integer not null check (sequence >= 0),
  node_key text not null,
  event_type text not null check (event_type in (
    'node_started',
    'node_completed',
    'node_failed',
    'retry_scheduled',
    'checkpoint_saved',
    'human_requested',
    'human_resolved',
    'run_status_changed'
  )),
  attempt integer not null default 1 check (attempt >= 0),
  status text not null check (status in (
    'pending', 'running', 'waiting_human', 'succeeded', 'failed', 'skipped'
  )),
  safe_payload jsonb not null default '{}'::jsonb,
  latency_ms integer check (latency_ms >= 0),
  input_tokens integer check (input_tokens >= 0),
  output_tokens integer check (output_tokens >= 0),
  cost_usd numeric(12,6) check (cost_usd >= 0),
  created_at timestamptz not null default now(),
  unique (run_id, sequence)
);

create table if not exists research_questions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  parent_id uuid references research_questions(id) on delete set null,
  source_run_id uuid not null references workflow_runs(id) on delete cascade,
  question text not null check (char_length(trim(question)) > 0),
  status text not null default 'planned'
    check (status in ('planned', 'active', 'answered', 'blocked', 'cancelled')),
  priority smallint not null default 0,
  plan_order integer not null check (plan_order >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique nulls not distinct (source_run_id, parent_id, plan_order)
);

create table if not exists claims (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  question_id uuid references research_questions(id) on delete set null,
  source_run_id uuid not null references workflow_runs(id) on delete cascade,
  text text not null check (char_length(trim(text)) > 0),
  normalized_key text not null,
  stance text not null default 'neutral'
    check (stance in ('supports', 'opposes', 'neutral')),
  confidence numeric(5,4) not null check (confidence between 0 and 1),
  review_status text not null default 'pending'
    check (review_status in ('pending', 'accepted', 'edited', 'rejected', 'invalidated')),
  source_version integer not null default 1 check (source_version > 0),
  invalidated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (project_id, normalized_key, source_version)
);

create table if not exists claim_evidence (
  claim_id uuid not null references claims(id) on delete cascade,
  citation_id uuid not null references citations(id) on delete cascade,
  relation text not null check (relation in ('supports', 'contradicts', 'mentions')),
  extraction_score numeric(5,4) not null check (extraction_score between 0 and 1),
  extractor_version text not null,
  created_at timestamptz not null default now(),
  primary key (claim_id, citation_id, relation)
);

create table if not exists claim_relations (
  source_claim_id uuid not null references claims(id) on delete cascade,
  target_claim_id uuid not null references claims(id) on delete cascade,
  relation text not null check (relation in ('supports', 'contradicts', 'duplicates')),
  confidence numeric(5,4) not null check (confidence between 0 and 1),
  rationale_summary text,
  created_at timestamptz not null default now(),
  primary key (source_claim_id, target_claim_id, relation),
  check (source_claim_id <> target_claim_id)
);

create table if not exists reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  source_run_id uuid not null references workflow_runs(id) on delete restrict,
  title text not null,
  status text not null default 'draft'
    check (status in ('draft', 'review', 'published', 'invalidated')),
  revision integer not null check (revision > 0),
  validation_status text not null default 'pending'
    check (validation_status in ('pending', 'passed', 'failed', 'retrying')),
  generated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (project_id, revision)
);

create table if not exists report_sections (
  id uuid primary key default gen_random_uuid(),
  report_id uuid not null references reports(id) on delete cascade,
  parent_section_id uuid references report_sections(id) on delete set null,
  section_key text not null,
  position integer not null check (position >= 0),
  heading text not null,
  body_markdown text not null,
  evidence_snapshot jsonb not null,
  validation_status text not null
    check (validation_status in ('pending', 'passed', 'failed', 'retrying')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (report_id, section_key),
  unique (report_id, position)
);

create table if not exists human_decisions (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references workflow_runs(id) on delete cascade,
  event_id bigint references run_events(id) on delete set null,
  user_id uuid not null references profiles(id) on delete restrict,
  interrupt_key text not null,
  decision text not null check (decision in ('approve', 'edit', 'reject')),
  proposed_payload jsonb not null,
  final_payload jsonb,
  reason text,
  created_at timestamptz not null default now(),
  unique (run_id, interrupt_key)
);

create table if not exists outbox_events (
  id uuid primary key default gen_random_uuid(),
  aggregate_type text not null,
  aggregate_id uuid not null,
  event_type text not null,
  payload jsonb not null,
  idempotency_key text not null unique,
  status text not null default 'pending'
    check (status in ('pending', 'publishing', 'published', 'failed')),
  attempts integer not null default 0 check (attempts >= 0),
  available_at timestamptz not null default now(),
  published_at timestamptz,
  last_error text,
  created_at timestamptz not null default now()
);

create table if not exists evaluation_datasets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid references projects(id) on delete set null,
  name text not null,
  version integer not null check (version > 0),
  status text not null default 'draft'
    check (status in ('draft', 'frozen', 'retired')),
  description text,
  created_at timestamptz not null default now(),
  unique (user_id, name, version)
);

create table if not exists evaluation_cases (
  id uuid primary key default gen_random_uuid(),
  dataset_id uuid not null references evaluation_datasets(id) on delete cascade,
  case_key text not null,
  input jsonb not null,
  expected_output jsonb,
  expected_evidence jsonb not null,
  labels text[] not null default '{}'::text[],
  created_at timestamptz not null default now(),
  unique (dataset_id, case_key)
);

create table if not exists evaluation_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid references projects(id) on delete set null,
  dataset_id uuid not null references evaluation_datasets(id) on delete restrict,
  pipeline_version_id uuid not null references pipeline_versions(id) on delete restrict,
  status text not null default 'pending'
    check (status in ('pending', 'running', 'succeeded', 'failed', 'cancelled')),
  idempotency_key text not null,
  summary jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (user_id, idempotency_key)
);

create table if not exists evaluation_scores (
  id uuid primary key default gen_random_uuid(),
  evaluation_run_id uuid not null references evaluation_runs(id) on delete cascade,
  case_id uuid not null references evaluation_cases(id) on delete restrict,
  metric_name text not null,
  metric_version text not null,
  value numeric,
  passed boolean,
  details jsonb not null default '{}'::jsonb,
  judge_model text,
  created_at timestamptz not null default now(),
  unique (evaluation_run_id, case_id, metric_name, metric_version),
  check (value is not null or passed is not null)
);

create index if not exists idx_workflow_runs_project_created
  on workflow_runs(project_id, created_at desc);
create index if not exists idx_workflow_runs_status_created
  on workflow_runs(status, created_at);
create index if not exists idx_run_events_run_node_attempt
  on run_events(run_id, node_key, attempt);
create index if not exists idx_run_events_created
  on run_events(created_at);
create index if not exists idx_research_questions_project_status
  on research_questions(project_id, status);
create index if not exists idx_research_questions_parent
  on research_questions(parent_id);
create index if not exists idx_claims_question
  on claims(question_id);
create index if not exists idx_claims_review_status
  on claims(project_id, review_status);
create index if not exists idx_claims_invalidation
  on claims(project_id, invalidated_at);
create index if not exists idx_claim_evidence_citation
  on claim_evidence(citation_id);
create index if not exists idx_claim_relations_target
  on claim_relations(target_claim_id);
create index if not exists idx_reports_project_status
  on reports(project_id, status);
create index if not exists idx_reports_source_run
  on reports(source_run_id);
create index if not exists idx_report_sections_parent
  on report_sections(parent_section_id);
create index if not exists idx_human_decisions_user_created
  on human_decisions(user_id, created_at desc);
create index if not exists idx_outbox_events_dispatch
  on outbox_events(status, available_at);
create index if not exists idx_evaluation_cases_labels
  on evaluation_cases using gin(labels);
create index if not exists idx_evaluation_runs_dataset
  on evaluation_runs(dataset_id);
create index if not exists idx_evaluation_runs_pipeline
  on evaluation_runs(pipeline_version_id);
create index if not exists idx_evaluation_runs_created
  on evaluation_runs(created_at desc);
create index if not exists idx_evaluation_scores_metric
  on evaluation_scores(metric_name, metric_version);
create index if not exists idx_evaluation_scores_case
  on evaluation_scores(case_id);

-- Close the four inherited-ownership gaps in the initial migration.
create policy document_pages_owner_select on document_pages
  for select
  using (
    exists (
      select 1 from documents
      where documents.id = document_pages.document_id
        and documents.user_id = auth.uid()
    )
  );

create policy tool_calls_owner_select on tool_calls
  for select
  using (
    exists (
      select 1 from ask_runs
      where ask_runs.id = tool_calls.ask_run_id
        and ask_runs.user_id = auth.uid()
    )
  );

create policy citations_owner_select on citations
  for select
  using (
    exists (
      select 1 from ask_runs
      where ask_runs.id = citations.ask_run_id
        and ask_runs.user_id = auth.uid()
    )
  );

create policy quiz_questions_owner_select on quiz_questions
  for select
  using (
    exists (
      select 1 from quiz_sets
      where quiz_sets.id = quiz_questions.quiz_set_id
        and quiz_sets.user_id = auth.uid()
    )
  );

alter table pipeline_versions enable row level security;
alter table workflow_runs enable row level security;
alter table run_events enable row level security;
alter table research_questions enable row level security;
alter table claims enable row level security;
alter table claim_evidence enable row level security;
alter table claim_relations enable row level security;
alter table reports enable row level security;
alter table report_sections enable row level security;
alter table human_decisions enable row level security;
alter table outbox_events enable row level security;
alter table evaluation_datasets enable row level security;
alter table evaluation_cases enable row level security;
alter table evaluation_runs enable row level security;
alter table evaluation_scores enable row level security;

create policy workflow_runs_owner_select on workflow_runs
  for select using (auth.uid() = user_id);
create policy workflow_runs_owner_insert on workflow_runs
  for insert with check (
    auth.uid() = user_id
    and exists (
      select 1 from projects
      where projects.id = workflow_runs.project_id
        and projects.user_id = auth.uid()
    )
  );

create policy run_events_owner_select on run_events
  for select using (
    exists (
      select 1 from workflow_runs
      where workflow_runs.id = run_events.run_id
        and workflow_runs.user_id = auth.uid()
    )
  );

create policy research_questions_owner_select on research_questions
  for select using (auth.uid() = user_id);

create policy claims_owner_select on claims
  for select using (auth.uid() = user_id);

create policy claim_evidence_owner_select on claim_evidence
  for select using (
    exists (
      select 1 from claims
      where claims.id = claim_evidence.claim_id
        and claims.user_id = auth.uid()
    )
    and exists (
      select 1
      from citations
      join ask_runs on ask_runs.id = citations.ask_run_id
      where citations.id = claim_evidence.citation_id
        and ask_runs.user_id = auth.uid()
    )
  );

create policy claim_relations_owner_select on claim_relations
  for select using (
    exists (
      select 1 from claims
      where claims.id = claim_relations.source_claim_id
        and claims.user_id = auth.uid()
    )
    and exists (
      select 1 from claims
      where claims.id = claim_relations.target_claim_id
        and claims.user_id = auth.uid()
    )
  );

create policy reports_owner_select on reports
  for select using (auth.uid() = user_id);

create policy report_sections_owner_select on report_sections
  for select using (
    exists (
      select 1 from reports
      where reports.id = report_sections.report_id
        and reports.user_id = auth.uid()
    )
  );

create policy human_decisions_owner_select on human_decisions
  for select using (
    exists (
      select 1 from workflow_runs
      where workflow_runs.id = human_decisions.run_id
        and workflow_runs.user_id = auth.uid()
    )
  );
create policy human_decisions_reviewer_insert on human_decisions
  for insert with check (
    auth.uid() = user_id
    and (
      exists (
        select 1 from workflow_runs
        where workflow_runs.id = human_decisions.run_id
          and workflow_runs.user_id = auth.uid()
      )
      or exists (
        select 1 from profiles
        where profiles.id = auth.uid()
          and profiles.role in ('developer', 'admin')
      )
    )
  );

create policy pipeline_versions_referenced_select on pipeline_versions
  for select using (
    created_by = auth.uid()
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
create policy pipeline_versions_developer_insert on pipeline_versions
  for insert
  with check (
    exists (
      select 1 from profiles
      where profiles.id = auth.uid()
        and profiles.role in ('developer', 'admin')
    )
    and created_by = auth.uid()
  );
create policy pipeline_versions_developer_update on pipeline_versions
  for update
  using (
    status in ('draft', 'candidate')
    and exists (
      select 1 from profiles
      where profiles.id = auth.uid()
        and profiles.role in ('developer', 'admin')
    )
  )
  with check (
    exists (
      select 1 from profiles
      where profiles.id = auth.uid()
        and profiles.role in ('developer', 'admin')
    )
    and status in ('draft', 'candidate', 'accepted', 'retired')
  );
create policy pipeline_versions_developer_delete on pipeline_versions
  for delete
  using (
    status <> 'accepted'
    and exists (
      select 1 from profiles
      where profiles.id = auth.uid()
        and profiles.role in ('developer', 'admin')
    )
  );

create policy evaluation_datasets_owner_select on evaluation_datasets
  for select using (auth.uid() = user_id);
create policy evaluation_datasets_owner_insert on evaluation_datasets
  for insert
  with check (
    auth.uid() = user_id
    and status = 'draft'
    and (
      project_id is null
      or exists (
        select 1 from projects
        where projects.id = evaluation_datasets.project_id
          and projects.user_id = auth.uid()
      )
    )
  );
create policy evaluation_datasets_owner_update on evaluation_datasets
  for update
  using (auth.uid() = user_id and status = 'draft')
  with check (
    auth.uid() = user_id
    and status in ('draft', 'frozen')
    and (
      project_id is null
      or exists (
        select 1 from projects
        where projects.id = evaluation_datasets.project_id
          and projects.user_id = auth.uid()
      )
    )
  );
create policy evaluation_datasets_owner_delete on evaluation_datasets
  for delete using (auth.uid() = user_id and status = 'draft');

create policy evaluation_cases_owner_select on evaluation_cases
  for select using (
    exists (
      select 1 from evaluation_datasets
      where evaluation_datasets.id = evaluation_cases.dataset_id
        and evaluation_datasets.user_id = auth.uid()
    )
  );
create policy evaluation_cases_owner_insert on evaluation_cases
  for insert with check (
    exists (
      select 1 from evaluation_datasets
      where evaluation_datasets.id = evaluation_cases.dataset_id
        and evaluation_datasets.user_id = auth.uid()
        and evaluation_datasets.status = 'draft'
    )
  );
create policy evaluation_cases_owner_update on evaluation_cases
  for update
  using (
    exists (
      select 1 from evaluation_datasets
      where evaluation_datasets.id = evaluation_cases.dataset_id
        and evaluation_datasets.user_id = auth.uid()
        and evaluation_datasets.status = 'draft'
    )
  )
  with check (
    exists (
      select 1 from evaluation_datasets
      where evaluation_datasets.id = evaluation_cases.dataset_id
        and evaluation_datasets.user_id = auth.uid()
        and evaluation_datasets.status = 'draft'
    )
  );
create policy evaluation_cases_owner_delete on evaluation_cases
  for delete using (
    exists (
      select 1 from evaluation_datasets
      where evaluation_datasets.id = evaluation_cases.dataset_id
        and evaluation_datasets.user_id = auth.uid()
        and evaluation_datasets.status = 'draft'
    )
  );

create policy evaluation_runs_owner_select on evaluation_runs
  for select using (auth.uid() = user_id);
create policy evaluation_runs_owner_insert on evaluation_runs
  for insert with check (
    auth.uid() = user_id
    and exists (
      select 1 from evaluation_datasets
      where evaluation_datasets.id = evaluation_runs.dataset_id
        and evaluation_datasets.user_id = auth.uid()
        and evaluation_datasets.status = 'frozen'
    )
  );

create policy evaluation_scores_owner_select on evaluation_scores
  for select using (
    exists (
      select 1 from evaluation_runs
      where evaluation_runs.id = evaluation_scores.evaluation_run_id
        and evaluation_runs.user_id = auth.uid()
    )
  );

-- No authenticated-user policy is intentionally defined for outbox_events.
-- The dispatcher uses the Supabase service role, which bypasses RLS.
