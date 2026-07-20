import { AuthGuard } from "@/components/auth-guard";
import { ControlPlaneDashboard } from "@/components/control-plane-dashboard";

export default function ControlPlanePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <ControlPlaneDashboard />}</AuthGuard>;
}
