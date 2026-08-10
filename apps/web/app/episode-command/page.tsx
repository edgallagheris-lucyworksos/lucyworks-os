import { AuthGuard } from "@/components/auth-guard";
import { EpisodeClientFinanceActions } from "@/components/episode-client-finance-actions";
import { EpisodeCommandShell } from "@/components/episode-command-shell";
import { EpisodeGovernancePanel } from "@/components/episode-governance-panel";
import { HospitalCommandWorkspace } from "@/components/hospital-command-workspace";

export default function EpisodeCommandPage() {
  return (
    <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"]}>
      <EpisodeCommandShell>
        <HospitalCommandWorkspace />
        <EpisodeGovernancePanel />
        <EpisodeClientFinanceActions />
      </EpisodeCommandShell>
    </AuthGuard>
  );
}
