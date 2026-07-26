import { AuthGuard } from "@/components/auth-guard";
import { OperationalWorkspaceV16 } from "@/components/operational-workspace-v16";

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
  return <AuthGuard allowedRoles={allowedRoles}><OperationalWorkspaceV16 /></AuthGuard>;
}
