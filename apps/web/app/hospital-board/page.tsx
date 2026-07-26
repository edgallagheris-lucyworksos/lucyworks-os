import { AuthGuard } from "@/components/auth-guard";
import { ResponsiveHospitalBoardV14 } from "@/components/responsive-hospital-board-v14";

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
      <ResponsiveHospitalBoardV14 />
    </AuthGuard>
  );
}
