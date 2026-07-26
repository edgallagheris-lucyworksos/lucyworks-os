import { AuthGuard } from "@/components/auth-guard";
import { HospitalMasterBoardV11 } from "@/components/hospital-master-board-v11";

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
      <HospitalMasterBoardV11 />
    </AuthGuard>
  );
}
