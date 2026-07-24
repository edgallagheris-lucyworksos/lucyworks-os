import { AuthGuard } from "@/components/auth-guard";
import { BvsConfigurationWorkspace } from "@/components/bvs-configuration-workspace";

export default function HospitalConfigurationPage() {
  return (
    <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"]}>
      <BvsConfigurationWorkspace />
    </AuthGuard>
  );
}
