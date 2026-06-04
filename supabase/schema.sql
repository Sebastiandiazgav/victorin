create extension if not exists pgcrypto;

create table if not exists public.capital_entries (
    id uuid primary key default gen_random_uuid(),
    entry_type text not null check (entry_type in ('initial', 'income_15', 'income_30')),
    amount numeric(14,2) not null check (amount >= 0),
    entry_date date not null default current_date,
    note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.loan_entries (
    id uuid primary key default gen_random_uuid(),
    entry_mode text not null check (entry_mode in ('detailed', 'aggregate')),
    borrower_name text,
    amount numeric(14,2) not null check (amount >= 0),
    loan_date date not null default current_date,
    note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint borrower_required_for_detailed check (
        (entry_mode = 'detailed' and borrower_name is not null and length(trim(borrower_name)) > 0)
        or entry_mode = 'aggregate'
    )
);

create index if not exists capital_entries_entry_date_idx on public.capital_entries(entry_date desc);
create index if not exists capital_entries_entry_type_idx on public.capital_entries(entry_type);
create index if not exists loan_entries_loan_date_idx on public.loan_entries(loan_date desc);
create index if not exists loan_entries_entry_mode_idx on public.loan_entries(entry_mode);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger capital_entries_updated_at
before update on public.capital_entries
for each row execute function public.set_updated_at();

create trigger loan_entries_updated_at
before update on public.loan_entries
for each row execute function public.set_updated_at();

alter table public.capital_entries enable row level security;
alter table public.loan_entries enable row level security;

create policy "Allow read capital entries" on public.capital_entries
for select using (true);
create policy "Allow write capital entries" on public.capital_entries
for all using (true) with check (true);

create policy "Allow read loan entries" on public.loan_entries
for select using (true);
create policy "Allow write loan entries" on public.loan_entries
for all using (true) with check (true);
