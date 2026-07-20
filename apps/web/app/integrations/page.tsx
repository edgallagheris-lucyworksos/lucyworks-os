import { AuthGuard } from "@/components/auth-guard";
import { IntegrationDashboard } from "@/components/integration-dashboard";

export default function IntegrationsPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "governance_lead", "hospital_director", "senior_clinician", "supervisor"]}><IntegrationDashboard /></AuthGuard>;
}
