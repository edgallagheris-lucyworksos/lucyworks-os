"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";

type WorkforceProfile = {
  staffRef: string;
  displayName: string;
  employmentStatus: string;
  primaryRoleRef: string;
  departmentRef: string;
  gradeOrTrainingLevel?: string;
  onCallEligible?: boolean;
  sourceStatus?: string;
};

type Competency = {
  staffRef: string;
  competencyRef: string;
  scopeRef: string;
  level: string;
  status: string;
  validUntil?: string;
};

type Shift = {
  shiftRef: string;
  staffRef: string;
  departmentRef: string;
  areaRef?: string;
  startsAt: string;
  endsAt: string;
  shiftType: string;
  status: string;
  onCall: boolean;
  sourceStatus: string;
};

type AvailabilityException = {
  exceptionRef: string;
  staffRef: string;
  startsAt: string;
  endsAt: string;
  exceptionType: string;
  status: string;
  detail?: string;
};

type RequirementAssessment = {
  requirement: {
    requirementRef?: string;
    serviceRef?: string;
    areaRef?: string;
    roleRef?: string;
    competencyRef?: string;
    minimumCount?: number;
  };
  eligibleStaffRefs: string[];
  eligibleCount: number;
  excluded: { staffRef: string; reason: string }[];
  gap: number;
  status: string;
};

type Dashboard = {
  workforce: WorkforceProfile[];
  competencies: Competency[];
  summary: { provisionalCompetencies: number; workforceProfiles: number };
};

type Roster = { shifts: Shift[]; availabilityExceptions: AvailabilityException[] };

type Assessment = {
  assessedAt: string;
  activeShiftCount: number;
  approvedExceptionCount: number;
  gapCount: number;
  safeToOperate: boolean;
  requirements: RequirementAssessment[];
  staffRisks: Record<string, { type: string; severity: string; [key: string]: unknown }[]>;
  unprofiledShifts: string[];
};

type WorkforceState = { dashboard: Dashboard; roster: Roster; assessment: Assessment };

function clock(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function label(value?: string) {
  return String(value || "not recorded").replaceAll("_", " ");
}

function isCurrent(shift: Shift, now: number) {
  return new Date(shift.startsAt).getTime() <= now && new Date(shift.endsAt).getTime() > now && ["planned", "active"].includes(shift.status);
}

export function HospitalWorkforce() {
  const [data, setData] = useState<WorkforceState | null>(null);
  const [status, setStatus] = useState("Loading workforce");
  const [query, setQuery] = useState("");
  const [department, setDepartment] = useState("all");
  const [exceptionOnly, setExceptionOnly] = useState(false);
  const operationalDate = localOperationalDate();

  const refresh = useCallback(async () => {
    const start = new Date(`${operationalDate}T00:00:00`);
    const end = new Date(start);
    end.setDate(end.getDate() + 1);
    try {
      const [dashboard, roster, assessment] = await Promise.all([
        apiGet<Dashboard>("/api/bvs-v6/dashboard"),
        apiGet<Roster>(`/api/bvs-v6/rota?startsAt=${encodeURIComponent(start.toISOString())}&endsAt=${encodeURIComponent(end.toISOString())}`),
        apiGet<Assessment>("/api/bvs-v6/rota/assessment"),
      ]);
      setData({ dashboard, roster, assessment });
      setStatus("Live");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Workforce state unavailable");
    }
  }, [operationalDate]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const now = Date.now();
  const departments = useMemo(() => [...new Set((data?.dashboard.workforce || []).map((person) => person.departmentRef))].sort(), [data]);
  const activeShifts = useMemo(() => (data?.roster.shifts || []).filter((shift) => isCurrent(shift, now)), [data, now]);
  const currentByStaff = useMemo(() => new Map(activeShifts.map((shift) => [shift.staffRef, shift])), [activeShifts]);
  const absenceByStaff = useMemo(() => new Map((data?.roster.availabilityExceptions || [])
    .filter((item) => item.status === "approved" && new Date(item.startsAt).getTime() <= now && new Date(item.endsAt).getTime() > now)
    .map((item) => [item.staffRef, item])), [data, now]);

  const people = useMemo(() => {
    if (!data) return [];
    const competencies = new Map<string, Competency[]>();
    for (const item of data.dashboard.competencies) competencies.set(item.staffRef, [...(competencies.get(item.staffRef) || []), item]);
    return data.dashboard.workforce
      .filter((person) => person.employmentStatus === "active")
      .map((person) => {
        const shift = currentByStaff.get(person.staffRef);
        const exception = absenceByStaff.get(person.staffRef);
        const skills = competencies.get(person.staffRef) || [];
        const verifiedSkills = skills.filter((item) => item.status === "verified");
        const risks = data.assessment.staffRisks[person.staffRef] || [];
        return { person, shift, exception, skills, verifiedSkills, risks };
      })
      .filter(({ person, shift, exception, skills }) => {
        if (department !== "all" && person.departmentRef !== department) return false;
        if (exceptionOnly && !exception) return false;
        const needle = query.trim().toLowerCase();
        if (!needle) return true;
        return [person.displayName, person.staffRef, person.primaryRoleRef, person.departmentRef, person.gradeOrTrainingLevel, shift?.areaRef, ...skills.map((item) => item.competencyRef)]
          .some((value) => String(value || "").toLowerCase().includes(needle));
      })
      .sort((left, right) => Number(!left.shift) - Number(!right.shift) || left.person.departmentRef.localeCompare(right.person.departmentRef) || left.person.displayName.localeCompare(right.person.displayName));
  }, [absenceByStaff, currentByStaff, data, department, exceptionOnly, query]);

  if (!data) return <section className="workforce loading"><style>{css}</style><b>Workforce and safe coverage</b><span>{status}</span><button onClick={() => void refresh()}>Retry</button></section>;

  const activePeople = data.dashboard.workforce.filter((person) => person.employmentStatus === "active").length;
  const activeAbsences = absenceByStaff.size;
  const gaps = data.assessment.requirements.filter((item) => item.status === "gap");

  return <main className="workforce">
    <style>{css}</style>
    <header className="workforceTitle">
      <div><span>Workforce command</span><h2>Workforce and safe coverage</h2><p>Profiles, verified competencies, live rota, absence and coverage requirements in one operational projection.</p></div>
      <div className="workforceActions"><span className={status === "Live" ? "live" : "warning"}>{status}</span><button onClick={() => void refresh()}>Refresh</button></div>
    </header>

    <section className="workforceSummary">
      <article><b>{activePeople}</b><span>active profiles</span></article>
      <article><b>{activeShifts.length}</b><span>on shift now</span></article>
      <article className={gaps.length ? "critical" : ""}><b>{data.assessment.gapCount}</b><span>coverage gaps</span></article>
      <article className={data.dashboard.summary.provisionalCompetencies ? "warning" : ""}><b>{data.dashboard.summary.provisionalCompetencies}</b><span>skills awaiting verification</span></article>
      <article className={activeAbsences ? "warning" : ""}><b>{activeAbsences}</b><span>unavailable now</span></article>
    </section>

    <section className="coveragePanel">
      <header><div><h3>Safe coverage assessment</h3><p>Shift-level requirements, verified competencies, absence and fatigue flags</p></div><strong className={data.assessment.safeToOperate ? "safe" : "unsafe"}>{data.assessment.safeToOperate ? "Coverage controls clear" : "Intervention required"}</strong></header>
      <div className="coverageRows">
        {data.assessment.requirements.map((item, index) => <article className={item.status === "gap" ? "gap" : ""} key={item.requirement.requirementRef || index}>
          <span><b>{label(item.requirement.serviceRef)}</b><small>{label(item.requirement.areaRef)} · {label(item.requirement.roleRef)}{item.requirement.competencyRef ? ` · ${label(item.requirement.competencyRef)}` : ""}</small></span>
          <span><strong>{item.eligibleCount}/{item.requirement.minimumCount || 0}</strong><small>eligible / required</small></span>
          <em>{item.gap ? `${item.gap} person gap` : "met"}</em>
        </article>)}
        {!data.assessment.requirements.length ? <p className="empty">No active coverage requirements are configured for this time.</p> : null}
      </div>
    </section>

    <section className="workforceFilters">
      <label><span>Find person or competency</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name, role, department, skill or staff reference" /></label>
      <label><span>Department</span><select value={department} onChange={(event) => setDepartment(event.target.value)}><option value="all">All departments</option>{departments.map((item) => <option value={item} key={item}>{label(item)}</option>)}</select></label>
      <label className="check"><input type="checkbox" checked={exceptionOnly} onChange={(event) => setExceptionOnly(event.target.checked)} /><span>Unavailable only</span></label>
    </section>

    <section className="workforceTableWrap">
      <table>
        <thead><tr><th>Person</th><th>Role / department</th><th>Duty now</th><th>Verified competencies</th><th>Availability / risk</th><th>Source</th></tr></thead>
        <tbody>{people.map(({ person, shift, exception, verifiedSkills, risks }) => <tr key={person.staffRef} className={exception || risks.some((risk) => risk.severity === "red") ? "riskRow" : ""}>
          <td><b>{person.displayName}</b><small>{person.staffRef}{person.gradeOrTrainingLevel ? ` · ${person.gradeOrTrainingLevel}` : ""}</small></td>
          <td><b>{label(person.primaryRoleRef)}</b><small>{label(person.departmentRef)}</small></td>
          <td><b>{shift ? `${clock(shift.startsAt)}–${clock(shift.endsAt)}` : "Not on shift"}</b><small>{shift ? `${label(shift.areaRef)} · ${label(shift.shiftType)}` : person.onCallEligible ? "On-call eligible" : "No active duty"}</small></td>
          <td><b>{verifiedSkills.length} verified</b><small>{verifiedSkills.slice(0, 3).map((item) => label(item.competencyRef)).join(" · ") || "No verified competency recorded"}</small></td>
          <td><b>{exception ? label(exception.exceptionType) : risks.length ? `${risks.length} workload flag${risks.length === 1 ? "" : "s"}` : "Available"}</b><small>{exception?.detail || risks.map((risk) => label(risk.type)).join(" · ") || "No active exception"}</small></td>
          <td><b>{label(person.sourceStatus)}</b><small>{shift ? `rota ${label(shift.sourceStatus)}` : "profile only"}</small></td>
        </tr>)}</tbody>
      </table>
      {!people.length ? <p className="empty">No workforce profiles match the current filters.</p> : null}
    </section>

    <footer><span>Assessed {new Date(data.assessment.assessedAt).toLocaleString()}</span><b>Source: authenticated workforce, rota and coverage services</b></footer>
  </main>;
}

const css = `
.workforce{display:grid;gap:9px;padding:12px 18px 28px;background:#eef2f7;color:#182c3f}.workforce.loading{margin:12px 18px;padding:18px;background:#fff;border:1px solid #d8e0e8;border-radius:10px;grid-template-columns:1fr auto auto;align-items:center}.workforce button{min-height:31px;padding:5px 8px;border:1px solid #cad5df;border-radius:6px;background:#fff;color:#294a64;font-size:9px;font-weight:800}.workforceTitle{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:12px 14px;background:#fff;border:1px solid #d8e0e8;border-radius:10px}.workforceTitle>div:first-child>span{color:#42657f;font-size:8px;font-weight:850;text-transform:uppercase;letter-spacing:.08em}.workforceTitle h2{margin:3px 0 0;font-size:20px;color:#17344e}.workforceTitle p{margin:3px 0 0;color:#718092;font-size:9px}.workforceActions{display:flex;gap:5px;align-items:center}.workforceActions>span{padding:5px 7px;border-radius:99px;font-size:8px;font-weight:850;text-transform:uppercase}.workforceActions .live{background:#e3f2ea;color:#28674d}.workforceActions .warning{background:#fff0da;color:#8c5a12}
.workforceSummary{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}.workforceSummary article{display:flex;align-items:baseline;gap:7px;padding:8px 10px;background:#fff;border:1px solid #d8e0e8;border-left:3px solid #64859d;border-radius:8px}.workforceSummary article.warning{border-left-color:#c77c14}.workforceSummary article.critical{border-left-color:#b63c38}.workforceSummary b{font-size:20px;color:#17344e}.workforceSummary span{font-size:8px;color:#68798a;text-transform:uppercase;font-weight:800}
.coveragePanel{background:#fff;border:1px solid #d8e0e8;border-radius:9px;overflow:hidden}.coveragePanel>header{display:flex;justify-content:space-between;align-items:center;padding:9px 11px;border-bottom:1px solid #e2e8ee}.coveragePanel h3{margin:0;font-size:13px;color:#17344e}.coveragePanel header p{margin:2px 0 0;font-size:8px;color:#748394}.coveragePanel header>strong{padding:5px 8px;border-radius:99px;font-size:8px;text-transform:uppercase}.coveragePanel .safe{background:#e1f1e8;color:#2b694f}.coveragePanel .unsafe{background:#f8dedd;color:#932e2b}.coverageRows{display:grid;grid-template-columns:repeat(3,1fr)}.coverageRows article{display:grid;grid-template-columns:1fr auto;gap:3px 8px;padding:9px 10px;border-right:1px solid #e8edf1;border-bottom:1px solid #e8edf1;border-left:3px solid #4f7f68}.coverageRows article.gap{border-left-color:#b63c38;background:#fffafa}.coverageRows b,.coverageRows strong{font-size:9px}.coverageRows small{display:block;margin-top:2px;color:#768697;font-size:8px}.coverageRows em{grid-column:2;font-size:8px;font-style:normal;color:#5b7183}
.workforceFilters{display:grid;grid-template-columns:minmax(280px,1fr) 210px auto;gap:6px;align-items:end;padding:7px;background:#fff;border:1px solid #d8e0e8;border-radius:8px}.workforceFilters label{display:grid;gap:3px;color:#65778a;font-size:8px;font-weight:800;text-transform:uppercase}.workforceFilters input,.workforceFilters select{width:100%;min-height:32px;padding:5px 7px;border:1px solid #cad5df;border-radius:5px;background:#fff;color:#182c3f;font-size:10px}.workforceFilters .check{display:flex;align-items:center;gap:6px;min-height:32px;padding:0 7px;border:1px solid #d8e0e8;border-radius:5px}.workforceFilters .check input{width:auto;min-height:auto}
.workforceTableWrap{max-height:62vh;overflow:auto;background:#fff;border:1px solid #d8e0e8;border-radius:9px}.workforceTableWrap table{width:100%;min-width:980px;border-collapse:separate;border-spacing:0;font-size:9px}.workforceTableWrap th{position:sticky;top:0;z-index:2;padding:6px 7px;text-align:left;background:#edf2f6;color:#637588;border-bottom:1px solid #d8e0e8;font-size:8px;text-transform:uppercase;letter-spacing:.04em}.workforceTableWrap td{padding:7px;border-bottom:1px solid #e8edf1;vertical-align:top}.workforceTableWrap tr.riskRow td:first-child{border-left:4px solid #b63c38}.workforceTableWrap b{display:block;font-size:9px;color:#20384c}.workforceTableWrap small{display:block;margin-top:2px;color:#788697;font-size:8px;line-height:1.25}.empty{padding:14px;color:#6c7c8e;font-size:10px}.workforce footer{display:flex;justify-content:space-between;padding:7px 9px;border:1px solid #d5dee6;border-radius:7px;background:#f8fafb;color:#69798a;font-size:8px}
@media(max-width:900px){.workforceSummary{grid-template-columns:repeat(3,1fr)}.coverageRows{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.workforce{padding:8px}.workforceTitle{display:grid}.workforceSummary{grid-template-columns:1fr 1fr}.coverageRows{grid-template-columns:1fr}.workforceFilters{grid-template-columns:1fr}.workforce footer{display:grid;gap:3px}}
`;
