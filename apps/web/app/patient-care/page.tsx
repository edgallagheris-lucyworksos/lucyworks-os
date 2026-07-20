import { AuthGuard } from "@/components/auth-guard";
import { PatientCareWorkflow } from "@/components/patient-care-workflow";

export default function PatientCarePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}><PatientCareWorkflow /></AuthGuard>;
}
