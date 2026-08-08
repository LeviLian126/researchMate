-- DB-1: Link profiles.id to auth.users(id) so Supabase user deletion cascades.

-- The initial schema declared profiles.id as a free uuid primary key with no FK to
-- auth.users; deleting a Supabase auth user leaves an orphan profile (and cascades
-- to projects/documents/etc. via the existing profiles(id) foreign keys). Add the FK
-- so auth.users deletion propagates to all owner-scoped data.

alter table profiles
  add constraint profiles_id_fk
  foreign key (id) references auth.users(id) on delete cascade;

-- Rollback:
--   alter table profiles drop constraint if exists profiles_id_fk;
