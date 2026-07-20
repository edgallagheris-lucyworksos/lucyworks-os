import { AuthGuard } from "@/components/auth-guard";
import { HospitalImportManager } from "@/components/hospital-import-manager";

export default function HospitalImportsPage() {
  return <AuthGuard allowedRoles={["admin", "ops_manager", "clinical_director", "hospital_director", "governance_lead", "senior_clinician", "supervisor"]}><HospitalImportManager /></AuthGuard>;
}
