import { AuthGuard } from "@/components/auth-guard";
import { AutomationOperatorControlV23 } from "@/components/automation-operator-control-v23";

const allowedRoles = [
  "admin",
  "clinical_director",
  "governance_lead",
  "hospital_director",
  "ops_manager",
  "senior_clinician",
  "supervisor",
];

export default function AutomationControlPage() {
  return <AuthGuard allowedRoles={allowedRoles}><AutomationOperatorControlV23 /></AuthGuard>;
}
