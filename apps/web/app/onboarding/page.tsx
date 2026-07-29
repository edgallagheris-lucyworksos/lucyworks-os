import { AuthGuard } from "@/components/auth-guard";
import { OrganisationOnboardingV27 } from "@/components/organisation-onboarding-v27";

const roles = [
  "admin",
  "clinical_director",
  "governance_lead",
  "hospital_director",
  "ops_manager",
  "supervisor",
  "hr",
];

export default function OnboardingPage() {
  return (
    <AuthGuard allowedRoles={roles}>
      <OrganisationOnboardingV27 />
    </AuthGuard>
  );
}
