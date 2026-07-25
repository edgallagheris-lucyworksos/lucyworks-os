import { AuthGuard } from "@/components/auth-guard";
import { ReferralIntakeWorkspace } from "@/components/referral-intake-workspace";

export default function ReferralIntakePage() {
  return <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "nurse", "ops_manager", "senior_clinician", "supervisor"]}>
    <ReferralIntakeWorkspace />
  </AuthGuard>;
}
