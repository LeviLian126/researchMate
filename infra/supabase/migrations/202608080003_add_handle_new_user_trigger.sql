-- DB-3: Auto-provision a profile row when Supabase Auth creates a user.
--
-- Without a handle_new_user trigger, every new authentication row leaves
-- profiles empty until application code happens to insert one; downstream
-- FKs on profiles(id) then fail or require defensive insertions. Run as
-- SECURITY DEFINER so the auth-issued INSERT can write to profiles under
-- RLS, and ON CONFLICT (id) DO NOTHING keeps replays idempotent.

create or replace function handle_new_user()
returns trigger as $$
begin
  insert into profiles (id, email, provider)
  values (new.id, new.email, new.provider)
  on conflict (id) do nothing;
  return new;
end;
$$ language plpgsql security definer
set search_path = public;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();

-- Rollback:
--   drop trigger if exists on_auth_user_created on auth.users;
--   drop function if exists handle_new_user();
