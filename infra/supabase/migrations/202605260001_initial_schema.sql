create extension if not exists pgcrypto;

create type project_status as enum ('active', 'deleting', 'deleted', 'expired');
create type document_status as enum ('uploaded', 'parsing', 'parsed', 'indexing', 'ready', 'failed', 'expired', 'deleted');
create type source_type as enum ('local_doc', 'web_page');
create type ask_status as enum ('pending', 'running', 'succeeded', 'failed');
create type validation_status as enum ('pending', 'passed', 'failed', 'retrying');
create type job_status as enum ('pending', 'running', 'succeeded', 'failed', 'cancelled');
create type quiz_question_type as enum ('single_choice', 'short_answer');
create type quiz_difficulty as enum ('easy', 'medium', 'hard');

create table if not exists profiles (
  id uuid primary key,
  email text,
  provider text,
  role text not null default 'user' check (role in ('user', 'developer', 'admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 120),
  status project_status not null default 'active',
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  filename text not null,
  file_type text not null check (file_type in ('pdf', 'docx', 'pptx')),
  mime_type text not null,
  size_bytes bigint not null check (size_bytes > 0 and size_bytes <= 26214400),
  r2_object_key text not null unique,
  parser text,
  status document_status not null default 'uploaded',
  error_message text,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists document_pages (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  page_no integer,
  slide_no integer,
  section_title text,
  text text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists chunks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  document_id uuid references documents(id) on delete cascade,
  source_type source_type not null,
  source_title text not null,
  page_no integer,
  slide_no integer,
  url text,
  text text not null,
  token_count integer not null default 0,
  qdrant_point_id text not null unique,
  metadata jsonb not null default '{}'::jsonb,
  expires_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  title text not null default 'Untitled conversation',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  conversation_id uuid references conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  created_at timestamptz not null default now()
);

create table if not exists ask_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  conversation_id uuid references conversations(id) on delete set null,
  message_id uuid references messages(id) on delete set null,
  message text not null,
  source_mode text not null check (source_mode in ('auto', 'local_only', 'web_only', 'hybrid')),
  task_type text not null check (task_type in ('answer', 'quiz')),
  resolved_mode text not null check (resolved_mode in ('auto', 'local_only', 'web_only', 'hybrid')),
  status ask_status not null default 'pending',
  validation_status validation_status not null default 'pending',
  latency_ms integer,
  token_usage jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now()
);

create table if not exists tool_calls (
  id uuid primary key default gen_random_uuid(),
  ask_run_id uuid not null references ask_runs(id) on delete cascade,
  tool_name text not null,
  input jsonb not null default '{}'::jsonb,
  output_summary jsonb,
  status text not null check (status in ('pending', 'running', 'succeeded', 'failed', 'skipped')),
  latency_ms integer,
  error_message text,
  created_at timestamptz not null default now()
);

create table if not exists citations (
  id uuid primary key default gen_random_uuid(),
  ask_run_id uuid not null references ask_runs(id) on delete cascade,
  chunk_id uuid references chunks(id) on delete set null,
  document_id uuid references documents(id) on delete set null,
  source_type source_type not null,
  page_no integer,
  slide_no integer,
  url text,
  quote text not null,
  claim_id text,
  created_at timestamptz not null default now()
);

create table if not exists quiz_sets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  ask_run_id uuid references ask_runs(id) on delete set null,
  title text not null,
  source_mode text not null check (source_mode in ('local_only', 'hybrid')),
  sources_summary jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists quiz_questions (
  id uuid primary key default gen_random_uuid(),
  quiz_set_id uuid not null references quiz_sets(id) on delete cascade,
  type quiz_question_type not null,
  question text not null,
  options jsonb,
  answer text not null,
  explanation text not null,
  difficulty quiz_difficulty not null default 'medium',
  source_citations jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  constraint single_choice_has_four_options check (
    type <> 'single_choice'
    or (jsonb_typeof(options) = 'array' and jsonb_array_length(options) = 4)
  )
);

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid references projects(id) on delete cascade,
  document_id uuid references documents(id) on delete cascade,
  type text not null,
  status job_status not null default 'pending',
  progress integer not null default 0 check (progress between 0 and 100),
  payload jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists deletion_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid references projects(id) on delete cascade,
  document_id uuid references documents(id) on delete cascade,
  status job_status not null default 'pending',
  target_types jsonb not null default '["db","r2","qdrant","redis"]'::jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists api_usage (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  usage_date date not null default current_date,
  kind text not null,
  count integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, usage_date, kind)
);

create index if not exists idx_projects_user_status on projects(user_id, status);
create index if not exists idx_documents_user_project_status on documents(user_id, project_id, status);
create index if not exists idx_document_pages_document on document_pages(document_id);
create index if not exists idx_chunks_user_project_source on chunks(user_id, project_id, source_type);
create index if not exists idx_chunks_document on chunks(document_id);
create index if not exists idx_ask_runs_user_project_created on ask_runs(user_id, project_id, created_at desc);
create index if not exists idx_tool_calls_run on tool_calls(ask_run_id);
create index if not exists idx_citations_run on citations(ask_run_id);
create index if not exists idx_quiz_sets_user_project_created on quiz_sets(user_id, project_id, created_at desc);
create index if not exists idx_jobs_user_status on jobs(user_id, status);
create index if not exists idx_deletion_jobs_status on deletion_jobs(status, created_at);
create index if not exists idx_api_usage_user_date_kind on api_usage(user_id, usage_date, kind);

create or replace function owner_user_id(target_project_id uuid)
returns uuid
language sql
stable
as $$
  select user_id from projects where id = target_project_id
$$;

alter table profiles enable row level security;
alter table projects enable row level security;
alter table documents enable row level security;
alter table document_pages enable row level security;
alter table chunks enable row level security;
alter table conversations enable row level security;
alter table messages enable row level security;
alter table ask_runs enable row level security;
alter table tool_calls enable row level security;
alter table citations enable row level security;
alter table quiz_sets enable row level security;
alter table quiz_questions enable row level security;
alter table jobs enable row level security;
alter table deletion_jobs enable row level security;
alter table api_usage enable row level security;

create policy profiles_owner_select on profiles for select using (auth.uid() = id);
create policy projects_owner_all on projects for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy documents_owner_all on documents for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy chunks_owner_all on chunks for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy conversations_owner_all on conversations for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy messages_owner_all on messages for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy ask_runs_owner_all on ask_runs for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy quiz_sets_owner_all on quiz_sets for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy jobs_owner_all on jobs for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy deletion_jobs_owner_all on deletion_jobs for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy api_usage_owner_all on api_usage for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

