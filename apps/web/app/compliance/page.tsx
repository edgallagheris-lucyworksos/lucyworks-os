import { AuthGuard } from "@/components/auth-guard";
import { ComplianceDashboard } from "@/components/compliance-dashboard";

export default function CompliancePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <ComplianceDashboard />}</AuthGuard>;
}
