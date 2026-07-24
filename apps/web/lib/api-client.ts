import { clearSession, getSession } from "@/lib/session";

// Use the same-origin Next.js /api rewrite by default. An explicit public API
// base may be supplied for deployments that intentionally expose the API on a
// separate origin.
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/$/, "");

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const session = getSession();
  const headers = new Headers(init.headers || {});
  if (session?.token) headers.set("Authorization", `Bearer ${session.token}`);
  if (init.body && !headers.has("Content-Type") && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const url = path.startsWith("http://") || path.startsWith("https://") ? path : `${API_BASE}${path}`;
  const response = await fetch(url, { ...init, headers });
  if (response.status === 401) {
    clearSession();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.assign("/login?reason=session-expired");
    }
  }
  return response;
}

export async function apiJson<T = Record<string, unknown>>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : `API request failed: ${response.status}`;
    throw new Error(detail);
  }
  return data as T;
}

export async function apiGet<T = Record<string, unknown>>(path: string): Promise<T> {
  return apiJson<T>(path, { cache: "no-store" });
}

export async function apiPost<T = Record<string, unknown>>(path: string, body: unknown): Promise<T> {
  return apiJson<T>(path, { method: "POST", body: JSON.stringify(body) });
}
