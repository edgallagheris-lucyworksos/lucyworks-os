import { AuthGuard } from "@/components/auth-guard";
import { HospitalOperatingBoard } from "@/components/hospital-operating-board";

export default function HospitalOpsPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "hospital_director", "senior_clinician", "supervisor", "clinician", "nurse", "admin"]}><HospitalOperatingBoard /></AuthGuard>;
}
