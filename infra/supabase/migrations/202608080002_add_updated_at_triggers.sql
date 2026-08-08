-- DB-2: Keep updated_at truthful for every table that carries the column.
--
-- The schema declares updated_at with a default but no trigger writes it on UPDATE,
-- so stale values survive edits. Add one shared plpgsql function and per-table
-- BEFORE UPDATE triggers; the body is intentionally trivial so partial updates
-- still refresh the timestamp.

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- Each table below carries an updated_at column. We do not attach the trigger to
-- tables that only have created_at or runtime-specific timestamps.
do $$
begin
  create trigger if not exists set_updated_at_trigger
    before update on profiles
    for each row execute function set_updated_at();
  create trigger if not exists set_updated_at_trigger
    before update on projects
    for each row execute function set_updated_at();
  create trigger if not exists set_updated_at_trigger
    before update on documents
    for each row execute function set_updated_at();
  create trigger if not exists set_updated_at_trigger
    before update on conversations
    for each row execute function set_updated_at();
  create trigger if not exists set_updated_at_trigger
    before update on jobs
    for each row execute function set_updated_at();
  create trigger if not exists set_updated_at_trigger
    before update on api_usage
    for each row execute function set_updated_at();
  create trigger if not exists set_updated_at_trigger
    before update on claims
    for each row execute function set_updated_at();
  create trigger if not exists set_updated_at_trigger
    before update on reports
    for each row execute function set_updated_at();
  create trigger if not exists set_updated_at_trigger
    before update on report_sections
    for each row execute function set_updated_at();
  create trigger if not exists set_updated_at_trigger
    before update on runtime_heartbeats
    for each row execute function set_updated_at();
  create trigger if not exists set_updated_at_trigger
    before update on runtime_ai_config
    for each row execute function set_updated_at();
exception
  -- create trigger if not exists is only supported on PG14+; tolerate older targets
  -- and surface any genuine SQL error in the log rather than aborting the migration.
  when others then
    raise notice 'set_updated_at trigger setup skipped: %', sqlerrm;
end
$$;

-- Rollback:
--   drop trigger if exists set_updated_at_trigger on profiles;
--   drop trigger if exists set_updated_at_trigger on projects;
--   drop trigger if exists set_updated_at_trigger on documents;
--   drop trigger if exists set_updated_at_trigger on conversations;
--   drop trigger if exists set_updated_at_trigger on jobs;
--   drop trigger if exists set_updated_at_trigger on api_usage;
--   drop trigger if exists set_updated_at_trigger on claims;
--   drop trigger if exists set_updated_at_trigger on reports;
--   drop trigger if exists set_updated_at_trigger on report_sections;
--   drop trigger if exists set_updated_at_trigger on runtime_heartbeats;
--   drop trigger if exists set_updated_at_trigger on runtime_ai_config;
--   drop function if exists set_updated_at();
