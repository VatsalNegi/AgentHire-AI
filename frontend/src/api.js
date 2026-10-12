import { supabase } from "./supabaseClient";

const API_URL = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export async function apiRequest(path, options = {}, accessToken) {
  const headers = new Headers(options.headers || {});
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
      ...(accessToken ? { cache: "no-store" } : {}),
    });
  } catch {
    throw new Error(
      "Could not reach the interview service. Check your connection and try again."
    );
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      typeof data.detail === "string"
        ? data.detail
        : "The request failed. Please try again."
    );
    error.status = response.status;
    throw error;
  }
  return data;
}

export async function authenticatedRequest(
  path,
  options,
  accessToken,
  onSessionExpired
) {
  let token = accessToken;
  if (!token) {
    const { data, error } = await supabase.auth.getSession();
    if (error || !data.session?.access_token) {
      await onSessionExpired();
      throw new Error(
        "Your session expired. Sign in again to continue.",
        { cause: error }
      );
    }
    token = data.session.access_token;
  }

  try {
    return await apiRequest(path, options, token);
  } catch (requestError) {
    if (requestError.status !== 401) throw requestError;

    const { data, error } = await supabase.auth.refreshSession();
    if (error || !data.session?.access_token) {
      await onSessionExpired();
      throw new Error(
        "Your session expired. Sign in again to continue.",
        { cause: requestError }
      );
    }

    try {
      return await apiRequest(path, options, data.session.access_token);
    } catch (retryError) {
      if (retryError.status === 401) {
        await onSessionExpired();
        throw new Error(
          "Your session expired. Sign in again to continue.",
          { cause: retryError }
        );
      }
      throw retryError;
    }
  }
}
