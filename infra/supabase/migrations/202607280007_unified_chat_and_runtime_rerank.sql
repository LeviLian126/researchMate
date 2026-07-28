alter table conversations
  add column if not exists summary_text text,
  add column if not exists summary_token_count integer not null default 0
    check (summary_token_count >= 0),
  add column if not exists summary_message_count integer not null default 0
    check (summary_message_count >= 0),
  add column if not exists summary_updated_at timestamptz;

alter table messages
  add column if not exists ask_run_id uuid references ask_runs(id) on delete set null;

create index if not exists idx_messages_conversation_created
  on messages(conversation_id, created_at, id);
create index if not exists idx_messages_ask_run on messages(ask_run_id);

alter table ask_runs
  add column if not exists web_enabled boolean not null default false,
  add column if not exists context_strategy text not null default 'chat'
    check (context_strategy in (
      'chat','full_context','hybrid_retrieval','web','hybrid_retrieval_web','quiz'
    )),
  add column if not exists rerank_provider text
    check (rerank_provider in ('qdrant','nvidia','deterministic')),
  add column if not exists rerank_config_version integer check (rerank_config_version >= 1),
  add column if not exists rerank_degraded boolean not null default false,
  add column if not exists fallback_reason text;

update ask_runs
set web_enabled = source_mode in ('web_only','hybrid'),
    context_strategy = case
      when task_type = 'quiz' then 'quiz'
      when source_mode = 'web_only' then 'web'
      when source_mode = 'hybrid' then 'hybrid_retrieval_web'
      else 'hybrid_retrieval'
    end
where context_strategy = 'chat';

-- Expand phase: defaults let the previous runtime coexist until the contract migration.
alter table ask_runs alter column source_mode set default 'local_only';
alter table ask_runs alter column resolved_mode set default 'local_only';
alter table quiz_sets alter column source_mode set default 'local_only';

create table if not exists runtime_ai_config (
  config_key text primary key,
  provider text not null check (provider in ('auto','qdrant','nvidia','deterministic')),
  version integer not null default 1 check (version >= 1),
  updated_at timestamptz not null default now(),
  updated_by uuid references profiles(id) on delete set null
);

insert into runtime_ai_config(config_key,provider)
values ('rerank','auto')
on conflict (config_key) do nothing;

alter table runtime_ai_config enable row level security;

drop policy if exists runtime_ai_config_admin_read on runtime_ai_config;
create policy runtime_ai_config_admin_read on runtime_ai_config
  for select using (
    exists (
      select 1 from profiles
      where profiles.id = auth.uid()
        and profiles.role in ('developer','admin')
    )
  );

drop policy if exists runtime_ai_config_admin_write on runtime_ai_config;
create policy runtime_ai_config_admin_write on runtime_ai_config
  for update using (
    exists (
      select 1 from profiles
      where profiles.id = auth.uid()
        and profiles.role in ('developer','admin')
    )
  ) with check (
    exists (
      select 1 from profiles
      where profiles.id = auth.uid()
        and profiles.role in ('developer','admin')
    )
  );
