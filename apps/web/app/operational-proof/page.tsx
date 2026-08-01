import { AuthGuard } from "@/components/auth-guard";
import { OperationalProofV30 } from "@/components/operational-proof-v30";

const roles = [
  "hospital_director",
  "clinical_director",
  "ops_manager",
  "senior_clinician",
  "supervisor",
  "clinician",
  "nurse",
  "admin",
  "viewer",
];

export default function OperationalProofPage() {
  return <AuthGuard allowedRoles={roles}><OperationalProofV30 /></AuthGuard>;
}
