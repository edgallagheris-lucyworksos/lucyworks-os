import { AuthGuard } from "@/components/auth-guard";
import { ApprovalDashboard } from "@/components/approval-dashboard";

export default function ApprovalsPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}><ApprovalDashboard /></AuthGuard>;
}
