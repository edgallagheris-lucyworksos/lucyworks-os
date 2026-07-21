import { AuthGuard } from "@/components/auth-guard";
import { HospitalIntelligencePanel } from "@/components/hospital-intelligence-panel";

export default function HospitalIntelligencePage() {
  return (
    <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "pca", "radiographer", "senior_clinician", "supervisor"]}>
      <HospitalIntelligencePanel />
    </AuthGuard>
  );
}
