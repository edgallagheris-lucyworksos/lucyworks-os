import type { ReactNode } from "react";
import { MedicationShortcutV18 } from "@/components/medication-shortcut-v18";

export default function SystemControlLayout({ children }: { children: ReactNode }) {
  return <><MedicationShortcutV18 showProtocols />{children}</>;
}
