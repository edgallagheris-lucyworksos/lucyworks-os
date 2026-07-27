import { Suspense, type ReactNode } from "react";
import { MedicationShortcutV18 } from "@/components/medication-shortcut-v18";

export default function CareLayout({ children }: { children: ReactNode }) {
  return <><Suspense fallback={null}><MedicationShortcutV18 /></Suspense>{children}</>;
}
