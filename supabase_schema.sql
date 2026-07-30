create extension if not exists pgcrypto;

create table if not exists organizations (
  id uuid primary key,
  name text not null,
  slug text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists organization_members (
  id uuid primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  user_id text not null,
  role text not null default 'member',
  created_at timestamptz not null default now(),
  unique (organization_id, user_id)
);

create table if not exists projects (
  id uuid primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  owner_user_id text not null,
  name text not null,
  cohort_year integer,
  cohort_size integer not null default 0,
  status text not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists project_uploads (
  id uuid primary key,
  project_id uuid not null references projects(id) on delete cascade,
  organization_id uuid not null references organizations(id) on delete cascade,
  component text not null,
  filename text not null,
  storage_path text not null,
  content_type text not null,
  size_bytes bigint not null,
  file_ext text not null,
  source_kind text not null,
  row_count integer,
  parsed_summary jsonb,
  uploaded_by text not null,
  created_at timestamptz not null default now()
);

create table if not exists project_analyses (
  id uuid primary key,
  project_id uuid not null unique references projects(id) on delete cascade,
  organization_id uuid not null references organizations(id) on delete cascade,
  calculated_at timestamptz not null default now(),
  payload jsonb not null
);

create table if not exists reports (
  id uuid primary key,
  project_id uuid not null references projects(id) on delete cascade,
  organization_id uuid not null references organizations(id) on delete cascade,
  type text not null,
  narrative_payload jsonb,
  storage_path text not null,
  created_by text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_projects_org on projects (organization_id);
create index if not exists idx_uploads_project on project_uploads (project_id, component);
create index if not exists idx_reports_project on reports (project_id, created_at desc);
