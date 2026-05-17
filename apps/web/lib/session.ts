export type SessionUser = {
  id: number;
  name: string;
  role: string;
  email: string;
};

const SESSION_KEY = "lucyworks_session";

export function saveSession(user: SessionUser, token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SESSION_KEY, JSON.stringify({ user, token }));
}

export function getSession(): { user: SessionUser; token: string } | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(SESSION_KEY);
}
