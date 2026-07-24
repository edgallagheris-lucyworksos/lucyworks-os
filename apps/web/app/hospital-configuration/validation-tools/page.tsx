import { AuthGuard } from "@/components/auth-guard";
import { BvsValidationTools } from "@/components/bvs-validation-tools";

export default function BvsValidationToolsPage() {
  return (
    <AuthGuard allowedRoles={["admin", "clinical_director", "governance_lead", "hospital_director", "ops_manager", "supervisor"]}>
      <BvsValidationTools />
    </AuthGuard>
  );
}
