-- Contract phase: the unified runtime is live before these retired columns are removed.
alter table ask_runs
  drop column if exists source_mode,
  drop column if exists resolved_mode;

alter table quiz_sets
  drop column if exists source_mode;
