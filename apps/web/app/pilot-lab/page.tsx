import { AuthGuard } from "@/components/auth-guard";
import { HospitalPilotLabV29 } from "@/components/hospital-pilot-lab-v29";

const roles = [
  "admin", "ops_manager", "hospital_director", "governance_lead", "clinical_director",
  "senior_clinician", "supervisor", "clinician", "nurse",
];

export default function PilotLabPage() {
  return (
    <AuthGuard allowedRoles={roles}>
      <HospitalPilotLabV29 />
    </AuthGuard>
  );
}
