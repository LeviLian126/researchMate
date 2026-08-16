-- Lightweight chunks remain queryable through direct context injection and do not
-- have a corresponding Qdrant point. PostgreSQL unique constraints permit multiple
-- NULL values, so the existing uniqueness contract remains valid for vector chunks.

alter table chunks alter column qdrant_point_id drop not null;
