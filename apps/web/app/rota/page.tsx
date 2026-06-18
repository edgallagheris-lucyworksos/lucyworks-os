"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { RotaCommandGrid } from "@/components/rota-command-grid";
import { RotaPressurePanel } from "@/components/rota-pressure-panel";

export default function RotaPage() {
  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="ROTA" subtitle="staffing grid, department cover and daily risk">
          <RotaPressurePanel />
          <RotaCommandGrid />
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
