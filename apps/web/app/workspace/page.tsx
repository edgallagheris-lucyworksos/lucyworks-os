import { AuthGuard } from "@/components/auth-guard";
import { OperationalWorkspaceV15 } from "@/components/operational-workspace-v15";

const allowedRoles = [
  "admin",
  "clinician",
  "clinical_director",
  "governance_lead",
  "hospital_director",
  "nurse",
  "ops_manager",
  "senior_clinician",
  "supervisor",
];

export default function WorkspacePage() {
  return <AuthGuard allowedRoles={allowedRoles}><OperationalWorkspaceV15 /></AuthGuard>;
}
