create extension if not exists "uuid-ossp";

create table if not exists groups (
  id uuid primary key default uuid_generate_v4(),
  code text unique not null,
  name text not null,
  created_at timestamptz default now()
);

create table if not exists members (
  id uuid primary key default uuid_generate_v4(),
  group_id uuid not null references groups(id) on delete cascade,
  display_name text not null,
  created_at timestamptz default now()
);

create table if not exists expenses (
  id uuid primary key default uuid_generate_v4(),
  group_id uuid not null references groups(id) on delete cascade,
  payer_id uuid not null references members(id) on delete cascade,
  description text not null,
  amount_paise int not null,
  split_type text not null default 'equal',
  created_at timestamptz default now()
);

create table if not exists expense_splits (
  id uuid primary key default uuid_generate_v4(),
  expense_id uuid not null references expenses(id) on delete cascade,
  member_id uuid not null references members(id) on delete cascade,
  share_paise int not null
);

create index if not exists idx_members_group on members(group_id);
create index if not exists idx_expenses_group on expenses(group_id);
create index if not exists idx_splits_expense on expense_splits(expense_id);
