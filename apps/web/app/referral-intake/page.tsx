import { AuthGuard } from "@/components/auth-guard";
import { GuidedReferralIntakeV31 } from "@/components/guided-referral-intake-v31";

export default function ReferralIntakePage() {
  return <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "nurse", "ops_manager", "senior_clinician", "supervisor"]}>
    <GuidedReferralIntakeV31 />
  </AuthGuard>;
}
