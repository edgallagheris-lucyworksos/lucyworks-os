import { clearSession } from "@/lib/session";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/$/, "");

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${encodeURIComponent(name)}=`;
  const part = document.cookie.split(";").map(value => value.trim()).find(value => value.startsWith(prefix));
  return part ? decodeURIComponent(part.slice(prefix.length)) : null;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  if (init.body && !headers.has("Content-Type") && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const method = (init.method || "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = readCookie("lucyworks_csrf");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  const url = path.startsWith("http://") || path.startsWith("https://") ? path : `${API_BASE}${path}`;
  const response = await fetch(url, { ...init, headers, credentials: "include" });
  if (response.status === 401) {
    clearSession();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.assign("/login?reason=session-expired");
    }
  }
  return response;
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : data?.detail ? JSON.stringify(data.detail) : `API request failed: ${response.status}`;
    throw new Error(detail);
  }
  return data as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return apiJson<T>(path, { cache: "no-store" });
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return apiJson<T>(path, { method: "POST", body: JSON.stringify(body) });
}
