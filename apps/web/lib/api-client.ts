import { apiFetch as sharedApiFetch, API_BASE } from "@/lib/api";

export { API_BASE };

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return sharedApiFetch(path, init);
}

export async function apiJson<T = Record<string, unknown>>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : data?.detail ? JSON.stringify(data.detail) : `API request failed: ${response.status}`;
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
