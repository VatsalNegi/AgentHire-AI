import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL?.trim() || "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim() || "";

function isPublicSupabaseKey(key) {
  if (key.startsWith("sb_publishable_")) return true;

  const [header, payload, signature] = key.split(".");
  if (!header || !payload || !signature) return false;

  try {
    const normalizedPayload = payload
      .replace(/-/g, "+")
      .replace(/_/g, "/")
      .padEnd(Math.ceil(payload.length / 4) * 4, "=");
    return JSON.parse(atob(normalizedPayload)).role === "anon";
  } catch {
    return false;
  }
}

function validateProjectUrl(value) {
  try {
    const url = new URL(value);
    const localHost = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    return (
      (url.protocol === "https:" || (localHost && url.protocol === "http:")) &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash &&
      (url.pathname === "/" || url.pathname === "")
    );
  } catch {
    return false;
  }
}

let configurationError = "";
if (!supabaseUrl || !supabaseAnonKey) {
  configurationError =
    "Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in frontend/.env.";
} else if (!validateProjectUrl(supabaseUrl)) {
  configurationError =
    "VITE_SUPABASE_URL must be a Supabase project URL (HTTPS, or localhost for local development).";
} else if (!isPublicSupabaseKey(supabaseAnonKey)) {
  configurationError =
    "VITE_SUPABASE_ANON_KEY must contain a public anon or publishable key, never a service-role/secret key.";
}

let client = null;
if (!configurationError) {
  try {
    client = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        autoRefreshToken: true,
        detectSessionInUrl: true,
        persistSession: true,
      },
    });
  } catch {
    configurationError = "Supabase client initialization failed. Check the public project configuration.";
  }
}

export const supabase = client;
export const supabaseConfigured = Boolean(client);
export const supabaseConfigurationError = configurationError;
