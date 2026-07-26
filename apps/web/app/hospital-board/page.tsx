import { AuthGuard } from "@/components/auth-guard";
import { HospitalMasterBoardV11, masterBoardRoles } from "@/components/hospital-master-board-v11";

export default function HospitalBoardPage() {
  return (
    <AuthGuard allowedRoles={masterBoardRoles}>
      <HospitalMasterBoardV11 />
    </AuthGuard>
  );
}
