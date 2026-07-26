import { AuthGuard } from "@/components/auth-guard";
import { ResponsiveHospitalBoardV15 } from "@/components/responsive-hospital-board-v15";

const allowedRoles = [
  "admin",
  "clinician",
  "clinical_director",
  "hospital_director",
  "nurse",
  "ops_manager",
  "senior_clinician",
  "supervisor",
];

export default function HospitalBoardPage() {
  return (
    <AuthGuard allowedRoles={allowedRoles}>
      <ResponsiveHospitalBoardV15 />
    </AuthGuard>
  );
}
