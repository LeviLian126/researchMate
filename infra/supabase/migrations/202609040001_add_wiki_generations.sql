-- Track project knowledge freshness for fail-closed Wiki-first querying.

alter table projects
  add column if not exists knowledge_generation bigint not null default 0,
  add column if not exists wiki_generation bigint not null default 0;

alter table projects
  drop constraint if exists projects_wiki_generation_not_ahead;

alter table projects
  add constraint projects_wiki_generation_not_ahead
  check (wiki_generation <= knowledge_generation);

-- Existing corpora have not passed the incremental compiler's completeness check.
update chunks
set metadata = metadata || jsonb_build_object('knowledge_generation', 1)
where metadata ->> 'wiki_mode' is distinct from 'true'
  and not metadata ? 'knowledge_generation';

update projects p
set knowledge_generation = 1
where knowledge_generation = 0 and exists (
  select 1 from chunks c where c.project_id = p.id and c.user_id = p.user_id
    and c.metadata ->> 'wiki_mode' is distinct from 'true'
);

create unique index if not exists idx_chunks_project_canonical_wiki_title
  on chunks (user_id, project_id, lower(source_title))
  where document_id is null and metadata ->> 'wiki_mode' = 'true';
