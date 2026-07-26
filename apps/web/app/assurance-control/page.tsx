import { AuthGuard } from "@/components/auth-guard";
import { AssuranceControlWorkspaceV12, assuranceControlRoles } from "@/components/assurance-control-workspace-v12";

export default function AssuranceControlPage() {
  return <AuthGuard allowedRoles={assuranceControlRoles}><AssuranceControlWorkspaceV12 /></AuthGuard>;
}
