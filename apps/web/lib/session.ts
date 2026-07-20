export type SessionUser = {
  id: string | number;
  subject?: string;
  name: string;
  role: string;
  email?: string | null;
  issuer?: string | null;
  authSource?: string;
  verified?: boolean;
  expiresAt?: string | null;
};

export type LucyWorksSession = {
  user: SessionUser;
  token: string;
  expiresAt: string | null;
};

const SESSION_KEY = "lucyworks_session";

export function saveSession(user: SessionUser, token: string, expiresInSeconds?: number | null) {
  if (typeof window === "undefined") return;
  const expiresAt = user.expiresAt || (expiresInSeconds ? new Date(Date.now() + expiresInSeconds * 1000).toISOString() : null);
  window.localStorage.setItem(SESSION_KEY, JSON.stringify({ user: { ...user, expiresAt }, token, expiresAt }));
}

export function getSession(): LucyWorksSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const session = JSON.parse(raw) as LucyWorksSession;
    if (!session?.token || !session?.user) throw new Error("invalid session");
    if (session.expiresAt && new Date(session.expiresAt).getTime() <= Date.now()) {
      clearSession();
      return null;
    }
    return session;
  } catch {
    clearSession();
    return null;
  }
}

export function clearSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(SESSION_KEY);
}
