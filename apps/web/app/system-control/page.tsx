import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";

const daily = [
  { href: "/workspace", title: "Patient Command", description: "Start here. Every active patient, owner, location, time, next action and control gap." },
  { href: "/hospital-board", title: "Hospital Today", description: "Rooms, theatres, imaging, wards, staff, times, conflicts and emergency changes." },
  { href: "/referral-intake", title: "Referrals", description: "Create, identify, triage and accept incoming referrals without duplicate-patient ambiguity." },
  { href: "/input", title: "Quick Input", description: "Record an operational problem once and give it an owner, urgency, patient and place." },
  { href: "/safety-control", title: "Safety and Staff Concerns", description: "Report patient incidents, staff welfare, conduct, safeguarding or mixed concerns; protect first and prove the fix." },
  { href: "/care", title: "Care Brief", description: "Open an episode and answer who, what, where, when and how on one screen." },
];

const advanced = [
  ["/pilot-control", "Pilot and go-live control"], ["/automation-control", "Automation authority"], ["/episode-command", "Episode decisions"], ["/patient-record", "Patient record"], ["/clinical-execution", "Patient work"],
  ["/patient-record/controlled-actions", "Controlled clinical actions"], ["/control-plane", "Legacy governance controls"], ["/workforce-rota", "Workforce rota"],
  ["/access-review", "Access review"], ["/compliance-safety", "UK compliance and safety"], ["/assurance-control", "Deployment assurance"],
  ["/live-control", "Live events and recovery"], ["/shadow-mode", "Legacy shadow records"], ["/production-readiness", "Production readiness evidence"],
  ["/hospital-configuration", "Hospital configuration"], ["/hospital-configuration/validation-tools", "Configuration validation"],
  ["/hospital-imports", "Import and reconciliation"], ["/integrations", "Vendor integrations"], ["/approvals", "Approval queue"],
  ["/compliance", "Compliance evidence"], ["/hospital-intelligence", "Hospital intelligence"],
] as const;

const roles = ["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"];

export default function SystemControlPage() {
  return <AuthGuard allowedRoles={roles}>
    <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 10, fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
        <span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>LUCYWORKS OS</span>
        <h1 style={{ fontSize: "clamp(38px,8vw,72px)", lineHeight: .93, margin: "7px 0" }}>Choose the job, not the module</h1>
        <p style={{ color: "#b6c2d1", maxWidth: 850 }}>Daily staff should normally use Patient Command, Hospital Today, Referrals, Quick Input, Safety and Staff Concerns, and Care Brief. Technical, governance and deployment controls are kept below.</p>
      </header>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(230px,1fr))", gap: 9, marginTop: 9 }}>
        {daily.map(item => <Link key={item.href} href={item.href} style={{ display: "grid", gap: 7, minHeight: 150, padding: 15, background: "white", border: "1px solid #cbd5e1", borderTop: "6px solid #0f766e", borderRadius: 15, color: "#0f172a", textDecoration: "none" }}><strong style={{ fontSize: 25 }}>{item.title}</strong><span style={{ color: "#475569" }}>{item.description}</span><b style={{ alignSelf: "end", color: "#1d4ed8" }}>Open →</b></Link>)}
      </section>

      <details style={{ marginTop: 12, background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 13 }}>
        <summary style={{ cursor: "pointer", fontSize: 21, fontWeight: 900 }}>Advanced, governance and configuration tools</summary>
        <p style={{ color: "#64748b" }}>These are not the normal route for day-to-day patient care.</p>
        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))", gap: 7 }}>
          {advanced.map(([href, title]) => <Link key={href} href={href} style={{ padding: 11, background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, color: "#0f172a", textDecoration: "none", fontWeight: 850 }}>{title} →</Link>)}
        </section>
      </details>
    </main>
  </AuthGuard>;
}
