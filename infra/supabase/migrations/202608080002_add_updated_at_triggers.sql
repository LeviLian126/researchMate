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
declare
  target_table text;
begin
  foreach target_table in array array[
    'profiles',
    'projects',
    'documents',
    'conversations',
    'jobs',
    'api_usage',
    'claims',
    'reports',
    'report_sections',
    'runtime_heartbeats',
    'runtime_ai_config'
  ]
  loop
    if not exists (
      select 1
      from pg_trigger
      where tgname = 'set_updated_at_trigger'
        and tgrelid = to_regclass(target_table)
        and not tgisinternal
    ) then
      execute format(
        'create trigger set_updated_at_trigger before update on %I '
        'for each row execute function set_updated_at()',
        target_table
      );
    end if;
  end loop;
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
