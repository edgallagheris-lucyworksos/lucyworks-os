"use client";

import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function ManagerDashboardPage() {
  return (
    <HospitalShell title="Manager" subtitle="hospital overview and integrity risks">
      <LucyWorksCommandSurface mode="manager" />
    </HospitalShell>
  );
}
