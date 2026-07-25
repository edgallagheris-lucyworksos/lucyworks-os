import { AuthGuard } from "@/components/auth-guard";
import { DetailedControlledActions } from "@/components/detailed-controlled-actions";

export default function ControlledPatientRecordActionsPage() {
  return <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "ops_manager", "senior_clinician", "supervisor"]}><DetailedControlledActions /></AuthGuard>;
}
