import { Suspense } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { CareBriefV16 } from "@/components/care-brief-v16";

const roles = ["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"];

export default function CarePage() {
  return <AuthGuard allowedRoles={roles}><Suspense fallback={<main style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "#071019", color: "white", fontFamily: "system-ui", fontWeight: 900 }}>Loading care brief</main>}><CareBriefV16 /></Suspense></AuthGuard>;
}
