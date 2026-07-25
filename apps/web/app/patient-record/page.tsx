import { AuthGuard } from "@/components/auth-guard";
import { DetailedPatientRecordWorkspace } from "@/components/detailed-patient-record-workspace";

export default function PatientRecordPage() {
  return <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"]}><DetailedPatientRecordWorkspace /></AuthGuard>;
}
