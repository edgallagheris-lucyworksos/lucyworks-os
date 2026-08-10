import { AuthGuard } from "@/components/auth-guard";
import { EpisodeGovernancePanel } from "@/components/episode-governance-panel";
import { HospitalCommandWorkspace } from "@/components/hospital-command-workspace";

export default function EpisodeCommandPage() {
  return (
    <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"]}>
      <HospitalCommandWorkspace />
      <EpisodeGovernancePanel />
    </AuthGuard>
  );
}
