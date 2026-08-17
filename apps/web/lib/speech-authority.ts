import type { SessionUser } from "@/lib/session";

export const SPEECH_NOTICE_VERSION = "v19-recording-authority-1";
const STORAGE_KEY = "lucyworks_speech_authority_v19";

export type SpeechAuthority = {
  userId: string;
  userName: string;
  role: string;
  premisesRef: string;
  noticeVersion: string;
  acknowledgedAt: string;
};

export function readSpeechAuthority(user?: SessionUser | null, premisesRef?: string | null): SpeechAuthority | null {
  if (typeof window === "undefined" || !user) return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as SpeechAuthority;
    if (value.noticeVersion !== SPEECH_NOTICE_VERSION) return null;
    if (value.userId !== String(user.id)) return null;
    if (premisesRef && value.premisesRef !== premisesRef) return null;
    return value;
  } catch {
    return null;
  }
}

export function saveSpeechAuthority(user: SessionUser, premisesRef: string): SpeechAuthority {
  const value: SpeechAuthority = {
    userId: String(user.id),
    userName: user.name,
    role: user.role,
    premisesRef,
    noticeVersion: SPEECH_NOTICE_VERSION,
    acknowledgedAt: new Date().toISOString(),
  };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  return value;
}

export function clearSpeechAuthority() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}
