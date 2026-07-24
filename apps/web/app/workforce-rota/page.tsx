import { AuthGuard } from "@/components/auth-guard";
import { WorkforceRotaWorkspace } from "@/components/workforce-rota-workspace";

export default function WorkforceRotaPage() {
  return (
    <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"]}>
      <WorkforceRotaWorkspace />
    </AuthGuard>
  );
}
