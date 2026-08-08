-- DB-7: Index active conversations by owner and recency for chat history lookups.

-- Conversations are listed by user and recency; deleted_at filtering is the most
-- common predicate after user_id. A partial b-tree index on (user_id, created_at desc)
-- restricted to non-deleted rows supports list pages without scanning tombstones.

create index if not exists idx_conversations_user_created
  on conversations(user_id, created_at desc)
  where deleted_at is null;

-- Rollback:
--   drop index if exists idx_conversations_user_created;
