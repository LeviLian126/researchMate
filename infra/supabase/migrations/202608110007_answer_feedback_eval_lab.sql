-- Persist owner-scoped answer feedback and its immutable evaluation-case promotion state.

create table if not exists answer_feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  project_id uuid not null references projects(id) on delete cascade,
  conversation_id uuid not null references conversations(id) on delete cascade,
  ask_run_id uuid not null references ask_runs(id) on delete cascade,
  rating text not null check (rating in ('helpful', 'not_helpful')),
  category text check (category in (
    'incorrect_answer', 'incorrect_citation', 'missing_context',
    'irrelevant', 'unsafe', 'other'
  )),
  comment text check (comment is null or char_length(comment) <= 1000),
  question_snapshot text not null,
  answer_snapshot text not null,
  citation_chunk_ids uuid[] not null default '{}',
  retrieved_chunk_ids uuid[] not null default '{}',
  retrieved_evidence jsonb not null default '[]'::jsonb,
  status text not null default 'new' check (status in ('new', 'promoted')),
  promoted_case_id uuid references evaluation_cases(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, ask_run_id)
);

create index if not exists idx_answer_feedback_project_review
  on answer_feedback(user_id, project_id, rating, updated_at desc);

drop trigger if exists set_updated_at_trigger on answer_feedback;
create trigger set_updated_at_trigger before update on answer_feedback
  for each row execute function set_updated_at();

alter table answer_feedback enable row level security;

create policy answer_feedback_owner_select on answer_feedback
  for select using (auth.uid() = user_id);

create policy answer_feedback_owner_insert on answer_feedback
  for insert with check (
    auth.uid() = user_id
    and exists (
      select 1 from ask_runs
      where ask_runs.id = answer_feedback.ask_run_id
        and ask_runs.user_id = auth.uid()
        and ask_runs.project_id = answer_feedback.project_id
        and ask_runs.conversation_id = answer_feedback.conversation_id
    )
  );

create policy answer_feedback_owner_update on answer_feedback
  for update using (auth.uid() = user_id)
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from ask_runs
      where ask_runs.id = answer_feedback.ask_run_id
        and ask_runs.user_id = auth.uid()
        and ask_runs.project_id = answer_feedback.project_id
        and ask_runs.conversation_id = answer_feedback.conversation_id
    )
  );

create policy answer_feedback_owner_delete on answer_feedback
  for delete using (auth.uid() = user_id);

-- Rollback:
--   drop table if exists answer_feedback;
