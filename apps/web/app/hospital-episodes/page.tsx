import { AuthGuard } from "@/components/auth-guard";
import { HospitalEpisodeManager } from "@/components/hospital-episode-manager";

export default function HospitalEpisodesPage() {
  return <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"]}><HospitalEpisodeManager /></AuthGuard>;
}
