-- Add retrieval provenance without invalidating legacy chunks or historical citations.
alter table chunks add column if not exists section_title text;
alter table chunks add column if not exists section_path text[];
alter table chunks add column if not exists chunk_index integer;
alter table chunks add column if not exists char_start integer;
alter table chunks add column if not exists char_end integer;

alter table chunks drop constraint if exists chunks_char_range_valid;
alter table chunks add constraint chunks_char_range_valid check (
  (char_start is null and char_end is null)
  or (char_start is not null and char_end is not null and char_start >= 0 and char_end >= char_start)
);

create index if not exists chunks_document_chunk_index_idx
  on chunks (document_id, chunk_index)
  where document_id is not null and chunk_index is not null;

alter table citations add column if not exists section_title text;
