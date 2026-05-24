import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  const url = import.meta.env.PUBLIC_SUPABASE_URL?.trim();
  const key = import.meta.env.PUBLIC_SUPABASE_ANON_KEY?.trim();
  if (!url || !key) {
    return null;
  }
  if (!client) {
    client = createClient(url, key, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    });
  }
  return client;
}

export function isSupabaseConfigured(): boolean {
  return Boolean(
    import.meta.env.PUBLIC_SUPABASE_URL?.trim() &&
      import.meta.env.PUBLIC_SUPABASE_ANON_KEY?.trim(),
  );
}
