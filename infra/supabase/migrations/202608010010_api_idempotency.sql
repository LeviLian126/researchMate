-- Persists replay-safe request identities for cost-bearing Ask and Quiz operations.

create table if not exists api_idempotency (
  user_id uuid not null references profiles(id) on delete cascade,
  operation text not null check (operation in ('ask', 'quiz')),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 160),
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  state text not null check (state in ('pending', 'succeeded')),
  response jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, operation, idempotency_key),
  check ((state = 'pending' and response is null) or state = 'succeeded')
);

create index if not exists idx_api_idempotency_updated_at
  on api_idempotency (updated_at);

alter table api_idempotency enable row level security;

drop policy if exists api_idempotency_owner_all on api_idempotency;
create policy api_idempotency_owner_all on api_idempotency
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
