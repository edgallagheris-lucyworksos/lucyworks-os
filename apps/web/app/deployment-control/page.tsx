import { AuthGuard } from "@/components/auth-guard";
import { DeploymentControlV28 } from "@/components/deployment-control-v28";

const roles = [
  "admin", "ops_manager", "hospital_director", "governance_lead", "clinical_director",
  "senior_clinician", "supervisor", "clinician", "nurse",
];

export default function DeploymentControlPage() {
  return (
    <AuthGuard allowedRoles={roles}>
      <DeploymentControlV28 />
    </AuthGuard>
  );
}
