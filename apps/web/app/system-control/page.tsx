import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";

const daily = [
  { href: "/operating-context", title: "Hospital context", description: "Active organisation, site, premises and operating authority." },
  { href: "/workspace", title: "Patient workspace", description: "Active patients, owned actions, location, timing and control gaps." },
  { href: "/hospital-board", title: "Hospital operations", description: "Patient flow, rooms, theatres, imaging, wards, staffing and conflicts." },
  { href: "/referral-intake", title: "Referral intake", description: "Identity, owner authority, triage and referral decisions." },
  { href: "/input", title: "Quick input", description: "Record an operational issue once and assign ownership and urgency." },
  { href: "/safety-control", title: "Safety & staff concerns", description: "Patient incidents, staff welfare, conduct and safeguarding concerns." },
  { href: "/care", title: "Care brief", description: "One patient summary for lead, next action, location, timing and controls." },
];

const advanced = [
  ["/onboarding", "Organisation & hospital onboarding"],
  ["/deployment-control", "Hospital connections & speech"],
  ["/pilot-lab", "Integration test environment"],
  ["/operational-proof", "Operational proof"],
  ["/pilot-control", "Pilot & go-live control"],
  ["/automation-control", "Automation authority"],
  ["/episode-command", "Episode control"],
  ["/patient-record", "Patient record"],
  ["/clinical-execution", "Clinical work"],
  ["/patient-record/controlled-actions", "Controlled clinical actions"],
  ["/control-plane", "Governance controls"],
  ["/workforce-rota", "Workforce rota"],
  ["/access-review", "Access review"],
  ["/compliance-safety", "UK compliance & safety"],
  ["/assurance-control", "Deployment assurance"],
  ["/live-control", "Live events & recovery"],
  ["/shadow-mode", "Shadow-mode records"],
  ["/production-readiness", "Production readiness"],
  ["/hospital-configuration", "Hospital configuration"],
  ["/hospital-configuration/validation-tools", "Configuration validation"],
  ["/hospital-imports", "Import & reconciliation"],
  ["/integrations", "Vendor integrations"],
  ["/approvals", "Approval queue"],
  ["/compliance", "Compliance evidence"],
  ["/hospital-intelligence", "Hospital intelligence"],
] as const;

const roles = ["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor", "reception", "referral_coordinator", "insurance", "pharmacy", "laboratory", "imaging", "ward_assistant", "facilities", "hr", "finance", "viewer"];

export default function SystemControlPage() {
  return <AuthGuard allowedRoles={roles}>
    <main className="system-directory">
      <style>{css}</style>
      <header className="system-directory__header">
        <div><span>LucyWorks</span><h1>Operations directory</h1><p>Daily hospital work first. Governance, deployment and technical controls are separated below.</p></div>
        <nav><Link className="primary" href="/hospital-board">Hospital operations</Link><Link href="/workspace">Patient workspace</Link></nav>
      </header>

      <section className="system-directory__section">
        <header><div><span>Daily work</span><h2>Hospital workspaces</h2></div><small>{daily.length} areas</small></header>
        <div className="system-directory__grid">
          {daily.map(item => <Link key={item.href} href={item.href}><strong>{item.title}</strong><span>{item.description}</span><b>Open</b></Link>)}
        </div>
      </section>

      <details className="system-directory__advanced">
        <summary><div><span>Governance & administration</span><strong>Advanced controls</strong></div><small>{advanced.length} tools</small></summary>
        <p>Configuration, integrations, approvals, assurance and deployment controls for authorised staff.</p>
        <div>{advanced.map(([href, title]) => <Link key={href} href={href}>{title}<span>›</span></Link>)}</div>
      </details>
    </main>
  </AuthGuard>;
}

const css = `
.system-directory{display:grid;gap:12px;min-height:100vh;padding:14px 18px 30px;background:#eef2f7;color:#172033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.system-directory *{box-sizing:border-box}.system-directory__header{display:flex;justify-content:space-between;align-items:center;gap:18px;padding:14px 16px;background:#fff;border:1px solid #d9e1e9;border-radius:11px}.system-directory__header>div{max-width:720px}.system-directory__header span,.system-directory__section>header span,.system-directory__advanced summary span{display:block;color:#708095;font-size:9px;font-weight:850;text-transform:uppercase;letter-spacing:.09em}.system-directory__header h1{margin:3px 0;color:#142b40;font-size:24px;letter-spacing:-.025em}.system-directory__header p{margin:4px 0 0;color:#68788b;font-size:11px;line-height:1.45}.system-directory__header nav{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.system-directory__header nav a{padding:8px 10px;border:1px solid #cbd5df;border-radius:7px;background:#fff;color:#294761;text-decoration:none;font-size:10px;font-weight:800}.system-directory__header nav a.primary{border-color:#173f5f;background:#173f5f;color:#fff}.system-directory__section{background:#fff;border:1px solid #d9e1e9;border-radius:11px;overflow:hidden}.system-directory__section>header{display:flex;justify-content:space-between;align-items:end;padding:11px 13px;background:#f8fafc;border-bottom:1px solid #e7ecf1}.system-directory__section h2{margin:2px 0 0;color:#1a3247;font-size:16px}.system-directory__section header small{color:#7a8797;font-size:9px}.system-directory__grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:#e7ecf1}.system-directory__grid>a{display:grid;align-content:start;gap:5px;min-height:128px;padding:13px;background:#fff;color:#172033;text-decoration:none;border-top:3px solid #52738d}.system-directory__grid>a:first-child{border-top-color:#2d8061}.system-directory__grid>a:hover{background:#fafcfd}.system-directory__grid strong{font-size:13px;color:#1d364c}.system-directory__grid span{color:#68788b;font-size:10px;line-height:1.45}.system-directory__grid b{align-self:end;margin-top:auto;color:#2e5876;font-size:9px;text-transform:uppercase;letter-spacing:.05em}.system-directory__advanced{background:#fff;border:1px solid #d9e1e9;border-radius:11px;overflow:hidden}.system-directory__advanced summary{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 13px;cursor:pointer;list-style:none}.system-directory__advanced summary::-webkit-details-marker{display:none}.system-directory__advanced summary>div{display:grid;gap:2px}.system-directory__advanced summary strong{font-size:14px;color:#243b50}.system-directory__advanced summary small{color:#7d8998;font-size:9px}.system-directory__advanced>p{margin:0;padding:0 13px 10px;color:#6b798b;font-size:10px}.system-directory__advanced>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:#e7ecf1;border-top:1px solid #e7ecf1}.system-directory__advanced>div a{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:10px 11px;background:#fff;color:#294761;text-decoration:none;font-size:10px;font-weight:750}.system-directory__advanced>div a:hover{background:#f8fafc}.system-directory__advanced>div a span{font-size:15px;color:#8390a0}
@media(max-width:1050px){.system-directory__grid{grid-template-columns:repeat(2,1fr)}.system-directory__advanced>div{grid-template-columns:repeat(2,1fr)}}
@media(max-width:650px){.system-directory{padding:8px}.system-directory__header{display:grid}.system-directory__header nav{justify-content:flex-start}.system-directory__grid{grid-template-columns:1fr}.system-directory__grid>a{min-height:100px}.system-directory__advanced>div{grid-template-columns:1fr}}
`;
