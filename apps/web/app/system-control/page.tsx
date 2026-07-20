import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";

const surfaces = [
  { href: "/hospital-board", title: "Hospital master grid", description: "Canonical 15-minute operating plan with physical areas, conflicts and versioned commands." },
  { href: "/hospital-episodes", title: "Referral episodes", description: "Intake, ownership, governance gates and controlled phase transitions from referral to closure." },
  { href: "/patient-care", title: "Patient care evidence", description: "Consent, estimates, case communication, clinical/admin decisions and evidence timeline." },
  { href: "/control-plane", title: "Control plane", description: "Critical results, handovers, premises controls, service readiness and approvals." },
  { href: "/hospital-imports", title: "Import and reconciliation", description: "Preview exports, resolve unmatched rows and commit controlled canonical data." },
  { href: "/integrations", title: "Vendor integrations", description: "PIMS, imaging, laboratory and workforce connection health and provenance." },
  { href: "/approvals", title: "Approval queue", description: "Named senior decisions for overrides, red-risk evidence and governed AI." },
  { href: "/compliance", title: "Compliance evidence", description: "Evidence completeness, risks, estimates, consent and AI review state." },
];

export default function SystemControlPage() {
  return <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"]}>
    <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
        <span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em", textTransform: "uppercase" }}>LucyWorks OS</span>
        <h1 style={{ fontSize: "clamp(38px, 8vw, 72px)", lineHeight: .93, margin: "7px 0" }}>System control</h1>
        <p style={{ color: "#94a3b8", maxWidth: 850 }}>Open the real operational surfaces. The hospital board is the canonical source of planned work; governance and integration views support it rather than maintaining competing schedules.</p>
      </header>
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 10, marginTop: 10 }}>
        {surfaces.map((surface) => <Link key={surface.href} href={surface.href} style={{ display: "grid", gap: 7, minHeight: 145, padding: 16, background: "white", border: "1px solid #cbd5e1", borderRadius: 15, color: "#0f172a", textDecoration: "none", boxShadow: "0 6px 18px rgba(15,23,42,.05)" }}>
          <strong style={{ fontSize: 22 }}>{surface.title}</strong>
          <span style={{ color: "#475569" }}>{surface.description}</span>
          <b style={{ alignSelf: "end", color: "#2563eb" }}>Open →</b>
        </Link>)}
      </section>
    </main>
  </AuthGuard>;
}
