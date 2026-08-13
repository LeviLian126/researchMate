-- Add has_vector column to chunks table so lightweight documents can skip
-- embedding and Qdrant upsert during ingestion while remaining queryable
-- via direct context injection at query time.
alter table chunks add column if not exists has_vector boolean not null default true;

-- Partial index covering only lightweight chunks (has_vector = false) so the
-- query layer can efficiently separate lightweight from RAG chunks without
-- bloating the primary index that covers the majority of rows.
create index if not exists idx_chunks_document_has_vector
    on chunks(document_id, has_vector)
    where has_vector = false;
