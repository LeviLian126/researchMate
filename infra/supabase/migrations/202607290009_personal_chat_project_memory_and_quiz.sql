alter table projects
  add column if not exists kind text not null default 'workspace'
    check (kind in ('personal', 'workspace')),
  add column if not exists memory_summary_text text,
  add column if not exists memory_summary_token_count integer not null default 0
    check (memory_summary_token_count >= 0),
  add column if not exists memory_updated_at timestamptz;

create unique index if not exists idx_projects_one_personal_per_user
  on projects(user_id)
  where kind = 'personal' and deleted_at is null;

create index if not exists idx_projects_user_kind_updated
  on projects(user_id, kind, updated_at desc)
  where deleted_at is null;

alter table documents
  add column if not exists conversation_id uuid
    references conversations(id) on delete cascade;

create index if not exists idx_documents_conversation_status
  on documents(user_id, conversation_id, status)
  where deleted_at is null;

alter type quiz_question_type add value if not exists 'fill_blank';
alter type quiz_question_type add value if not exists 'subjective';
