export type SessionUser = {
  id: string | number;
  subject?: string;
  name: string;
  role: string;
  email?: string;
  issuer?: string | null;
  authSource?: string;
  verified?: boolean;
  expiresAt?: string | null;
};

export type LucyWorksSession = {
  user: SessionUser;
  expiresAt: string | null;
  /** Compatibility only. Browser bearer tokens are no longer persisted. */
  token?: undefined;
};

const SESSION_KEY = "lucyworks_session_user";

export function saveSession(user: SessionUser, _legacyToken?: string, expiresInSeconds?: number | null) {
  if (typeof window === "undefined") return;
  const expiresAt = user.expiresAt || (expiresInSeconds ? new Date(Date.now() + expiresInSeconds * 1000).toISOString() : null);
  const normalisedUser: SessionUser = { ...user, email: user.email || undefined, expiresAt };
  window.localStorage.setItem(SESSION_KEY, JSON.stringify({ user: normalisedUser, expiresAt }));
  // Remove the former bearer-token storage key during migration.
  window.localStorage.removeItem("lucyworks_session");
}

export function getSession(): LucyWorksSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const session = JSON.parse(raw) as LucyWorksSession;
    if (!session?.user) throw new Error("invalid session cache");
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
  window.localStorage.removeItem("lucyworks_session");
}
