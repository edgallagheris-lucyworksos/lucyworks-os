import { Suspense, type ReactNode } from "react";
import { MedicationShortcutV18 } from "@/components/medication-shortcut-v18";
import { SpeechShortcutV19 } from "@/components/speech-shortcut-v19";

export default function PatientRecordLayout({ children }: { children: ReactNode }) {
  return <><Suspense fallback={null}><MedicationShortcutV18 /><SpeechShortcutV19 mode="clinical_dictation" /></Suspense>{children}</>;
}
