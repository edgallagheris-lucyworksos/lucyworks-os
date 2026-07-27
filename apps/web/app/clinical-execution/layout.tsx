import type { ReactNode } from "react";
import { MedicationShortcutV18 } from "@/components/medication-shortcut-v18";

export default function ClinicalExecutionLayout({ children }: { children: ReactNode }) {
  return <><MedicationShortcutV18 />{children}</>;
}
