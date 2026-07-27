import { Suspense, type ReactNode } from "react";
import { MedicationShortcutV18 } from "@/components/medication-shortcut-v18";

export default function SystemControlLayout({ children }: { children: ReactNode }) {
  return <><Suspense fallback={null}><MedicationShortcutV18 showProtocols /></Suspense>{children}</>;
}
