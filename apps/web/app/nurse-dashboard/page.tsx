"use client";

import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function NurseDashboardPage() {
  return (
    <HospitalShell title="Nurse" subtitle="prep, meds, monitoring and handoffs">
      <LucyWorksCommandSurface mode="nurse" />
    </HospitalShell>
  );
}
