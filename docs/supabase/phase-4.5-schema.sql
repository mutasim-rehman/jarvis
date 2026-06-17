-- JARVIS Phase 4.5 — run once in Supabase Dashboard → SQL Editor
-- Safe to re-run: uses IF NOT EXISTS / OR REPLACE / ON CONFLICT DO NOTHING where possible.

-- ---------------------------------------------------------------------------
-- 1. Tables
-- ---------------------------------------------------------------------------

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  avatar_url text,
  created_at timestamptz default now()
);

create table if not exists public.preferences (
  user_id uuid primary key references auth.users (id) on delete cascade,
  settings jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

create table if not exists public.pairing_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users (id) on delete cascade,
  laptop_device_id uuid,
  pair_code text,
  expires_at timestamptz,
  used boolean default false
);

create table if not exists public.device_links (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users (id) on delete cascade,
  laptop_device_id uuid,
  phone_device_id uuid,
  status text default 'active',
  created_at timestamptz default now()
);

create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users (id) on delete cascade,
  target_device_id uuid,
  payload jsonb,
  status text default 'pending',
  created_at timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- 2. Default preference document (matches shared/preferences.py)
-- ---------------------------------------------------------------------------

create or replace function public.jarvis_default_preference_settings()
returns jsonb
language sql
immutable
as $$
  select '{
    "version": 1,
    "onboarding_completed": false,
    "sliders": {
      "honesty": 0.7,
      "humor": 0.4,
      "formality": 0.6,
      "verbosity": 0.5,
      "proactivity": 0.5
    },
    "assistant_defaults": {
      "tone": "calm",
      "verbosity": "moderate",
      "suggest_actions": true
    },
    "content_hints": {
      "genres": [],
      "interests": [],
      "do_not_suggest": []
    },
    "integrations": {
      "spotify": false,
      "youtube": false
    },
    "personality_profile_v1": null,
    "devices": [],
    "welcome_email_sent": false
  }'::jsonb;
$$;

-- ---------------------------------------------------------------------------
-- 3. Signup trigger — new auth.users → profiles + preferences
-- ---------------------------------------------------------------------------

create or replace function public.handle_new_jarvis_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, created_at)
  values (new.id, now())
  on conflict (id) do nothing;

  insert into public.preferences (user_id, settings, updated_at)
  values (new.id, public.jarvis_default_preference_settings(), now())
  on conflict (user_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created_jarvis on auth.users;

create trigger on_auth_user_created_jarvis
  after insert on auth.users
  for each row
  execute function public.handle_new_jarvis_user();

-- ---------------------------------------------------------------------------
-- 4. Backfill — users who signed up BEFORE the trigger existed
-- ---------------------------------------------------------------------------

insert into public.profiles (id, created_at)
select u.id, coalesce(u.created_at, now())
from auth.users u
where not exists (
  select 1 from public.profiles p where p.id = u.id
);

insert into public.preferences (user_id, settings, updated_at)
select u.id, public.jarvis_default_preference_settings(), now()
from auth.users u
where not exists (
  select 1 from public.preferences p where p.user_id = u.id
);

-- ---------------------------------------------------------------------------
-- 5. Row Level Security (hub / direct client access)
-- ---------------------------------------------------------------------------

alter table public.profiles enable row level security;
alter table public.preferences enable row level security;
alter table public.pairing_sessions enable row level security;
alter table public.device_links enable row level security;
alter table public.tasks enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
  for select using (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
  for update using (auth.uid() = id);

drop policy if exists "preferences_select_own" on public.preferences;
create policy "preferences_select_own" on public.preferences
  for select using (auth.uid() = user_id);

drop policy if exists "preferences_update_own" on public.preferences;
create policy "preferences_update_own" on public.preferences
  for update using (auth.uid() = user_id);

drop policy if exists "pairing_sessions_own" on public.pairing_sessions;
create policy "pairing_sessions_own" on public.pairing_sessions
  for all using (auth.uid() = user_id);

drop policy if exists "device_links_own" on public.device_links;
create policy "device_links_own" on public.device_links
  for all using (auth.uid() = user_id);

drop policy if exists "tasks_own" on public.tasks;
create policy "tasks_own" on public.tasks
  for all using (auth.uid() = user_id);

-- Backend uses SUPABASE_SERVICE_ROLE_KEY and bypasses RLS.

-- ---------------------------------------------------------------------------
-- 6. Verify (optional) — replace email with yours
-- ---------------------------------------------------------------------------
-- select u.id, u.email,
--        p.id is not null as has_profile,
--        pref.user_id is not null as has_preferences
-- from auth.users u
-- left join public.profiles p on p.id = u.id
-- left join public.preferences pref on pref.user_id = u.id
-- where u.email = 'you@example.com';
