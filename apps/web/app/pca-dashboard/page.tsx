"use client";

import { HospitalShell } from "@/components/hospital-shell";
import { LucyWorksCommandSurface } from "@/components/lucyworks-command-surface";

export default function PcaDashboardPage() {
  return (
    <HospitalShell title="PCA" subtitle="handoffs, assists and patient movement">
      <LucyWorksCommandSurface mode="pca" />
    </HospitalShell>
  );
}
