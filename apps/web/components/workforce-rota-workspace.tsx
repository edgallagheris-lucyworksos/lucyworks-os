"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiJson } from "@/lib/api-client";

type Roster = { shifts: Array<Record<string, any>>; availabilityExceptions: Array<Record<string, any>> };
type Assessment = { assessedAt: string; localAssessedAt: string; activeShiftCount: number; approvedExceptionCount: number; requirements: Array<Record<string, any>>; gapCount: number; staffRisks: Record<string, Array<Record<string, any>>>; safeToOperate: boolean; governanceNote: string };

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 16, padding: 16, boxShadow: "0 6px 18px rgba(15,23,42,.05)" };
const field: React.CSSProperties = { width: "100%", border: "1px solid #94a3b8", borderRadius: 9, padding: "9px 10px", background: "white", color: "#0f172a" };
const button: React.CSSProperties = { border: 0, borderRadius: 9, padding: "9px 12px", background: "#0f766e", color: "white", fontWeight: 800, cursor: "pointer" };

function toIso(localValue: string): string {
  return new Date(localValue).toISOString();
}

function defaultLocal(offsetHours: number): string {
  const date = new Date(Date.now() + offsetHours * 3600000);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function Badge({ value }: { value: string }) {
  const good = ["met", "active", "planned", "verified", "approved"].includes(value);
  const bad = ["gap", "cancelled", "sickness"].includes(value);
  const colour = good ? "#047857" : bad ? "#b91c1c" : "#a16207";
  return <span style={{ display: "inline-block", padding: "3px 7px", borderRadius: 999, background: `${colour}18`, color: colour, fontSize: 11, fontWeight: 900, textTransform: "uppercase" }}>{value.replaceAll("_", " ")}</span>;
}

export function WorkforceRotaWorkspace() {
  const [roster, setRoster] = useState<Roster>({ shifts: [], availabilityExceptions: [] });
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [shift, setShift] = useState({ shiftRef: "", staffRef: "", departmentRef: "", areaRef: "", startsAt: defaultLocal(0), endsAt: defaultLocal(8), shiftType: "standard", onCall: false });
  const [absence, setAbsence] = useState({ exceptionRef: "", staffRef: "", startsAt: defaultLocal(0), endsAt: defaultLocal(8), exceptionType: "leave", detail: "" });

  const load = useCallback(async () => {
    try {
      const start = new Date(Date.now() - 24 * 3600000).toISOString();
      const end = new Date(Date.now() + 7 * 24 * 3600000).toISOString();
      const [rosterData, assessmentData] = await Promise.all([
        apiGet<Roster>(`/api/bvs-v6/rota?startsAt=${encodeURIComponent(start)}&endsAt=${encodeURIComponent(end)}`),
        apiGet<Assessment>(`/api/bvs-v6/rota/assessment?at=${encodeURIComponent(new Date().toISOString())}`),
      ]);
      setRoster(rosterData);
      setAssessment(assessmentData);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load workforce rota");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function save(path: string, body: Record<string, any>, success: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(path, { method: "PUT", body: JSON.stringify(body) });
      setMessage(success);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rota action failed");
    } finally { setBusy(false); }
  }

  async function submitShift(event: FormEvent) {
    event.preventDefault();
    await save(`/api/bvs-v6/rota/shifts/${encodeURIComponent(shift.shiftRef)}`, { staffRef: shift.staffRef, departmentRef: shift.departmentRef, areaRef: shift.areaRef || undefined, startsAt: toIso(shift.startsAt), endsAt: toIso(shift.endsAt), shiftType: shift.shiftType, onCall: shift.onCall, status: "planned", sourceStatus: "draft", reason: "Rota shift entered for hospital verification" }, "Shift added to the governed rota.");
    setShift({ shiftRef: "", staffRef: "", departmentRef: "", areaRef: "", startsAt: defaultLocal(0), endsAt: defaultLocal(8), shiftType: "standard", onCall: false });
  }

  async function submitAbsence(event: FormEvent) {
    event.preventDefault();
    await save(`/api/bvs-v6/rota/availability/${encodeURIComponent(absence.exceptionRef)}`, { staffRef: absence.staffRef, startsAt: toIso(absence.startsAt), endsAt: toIso(absence.endsAt), exceptionType: absence.exceptionType, status: "approved", sourceStatus: "draft", detail: absence.detail, reason: "Availability exception entered for rota calculation" }, "Availability exception applied to safe coverage.");
    setAbsence({ exceptionRef: "", staffRef: "", startsAt: defaultLocal(0), endsAt: defaultLocal(8), exceptionType: "leave", detail: "" });
  }

  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}><div><span style={{ color: "#2dd4bf", fontWeight: 900, fontSize: 11, letterSpacing: ".12em", textTransform: "uppercase" }}>LucyWorks OS · Workforce v6</span><h1 style={{ margin: "5px 0", fontSize: "clamp(34px,7vw,66px)", lineHeight: .95 }}>Rota and safe staffing</h1></div><Link href="/hospital-configuration" style={{ color: "white", textDecoration: "none", border: "1px solid #334155", borderRadius: 9, padding: "8px 11px", alignSelf: "start" }}>← Hospital configuration</Link></div>
      <p style={{ color: "#94a3b8", maxWidth: 900 }}>Coverage is calculated from active shifts, approved availability exceptions, verified competencies, service requirements and configured fatigue thresholds.</p>
    </header>

    {error && <div style={{ ...panel, borderColor: "#fca5a5", color: "#991b1b", marginTop: 10 }}>{error}</div>}
    {message && <div style={{ ...panel, borderColor: "#86efac", color: "#166534", marginTop: 10 }}>{message}</div>}

    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 9, marginTop: 10 }}>
      <div style={panel}><small>Operating state</small><h2 style={{ margin: "5px 0", color: assessment?.safeToOperate ? "#047857" : "#b91c1c" }}>{assessment?.safeToOperate ? "COVERED" : "GAPS"}</h2></div>
      <div style={panel}><small>Active shifts</small><h2 style={{ margin: "5px 0" }}>{assessment?.activeShiftCount ?? 0}</h2></div>
      <div style={panel}><small>Coverage gaps</small><h2 style={{ margin: "5px 0", color: assessment?.gapCount ? "#b91c1c" : "#047857" }}>{assessment?.gapCount ?? 0}</h2></div>
      <div style={panel}><small>Availability exceptions</small><h2 style={{ margin: "5px 0" }}>{assessment?.approvedExceptionCount ?? 0}</h2></div>
    </section>

    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(320px,1fr))", gap: 10, marginTop: 10 }}>
      <form onSubmit={submitShift} style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Add shift</h2><input required style={field} placeholder="Stable shift reference" value={shift.shiftRef} onChange={e => setShift({ ...shift, shiftRef: e.target.value })} /><input required style={field} placeholder="Staff reference" value={shift.staffRef} onChange={e => setShift({ ...shift, staffRef: e.target.value })} /><input required style={field} placeholder="Department / service reference" value={shift.departmentRef} onChange={e => setShift({ ...shift, departmentRef: e.target.value })} /><input style={field} placeholder="Area reference, e.g. icu" value={shift.areaRef} onChange={e => setShift({ ...shift, areaRef: e.target.value })} /><label>Starts<input required type="datetime-local" style={field} value={shift.startsAt} onChange={e => setShift({ ...shift, startsAt: e.target.value })} /></label><label>Ends<input required type="datetime-local" style={field} value={shift.endsAt} onChange={e => setShift({ ...shift, endsAt: e.target.value })} /></label><select style={field} value={shift.shiftType} onChange={e => setShift({ ...shift, shiftType: e.target.value })}><option value="standard">Standard</option><option value="night">Night</option><option value="emergency">Emergency</option><option value="training">Training</option></select><label style={{ display: "flex", gap: 8 }}><input type="checkbox" checked={shift.onCall} onChange={e => setShift({ ...shift, onCall: e.target.checked })} /> On-call shift</label><button disabled={busy} style={button}>Save shift</button></form>
      <form onSubmit={submitAbsence} style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Add availability exception</h2><input required style={field} placeholder="Stable exception reference" value={absence.exceptionRef} onChange={e => setAbsence({ ...absence, exceptionRef: e.target.value })} /><input required style={field} placeholder="Staff reference" value={absence.staffRef} onChange={e => setAbsence({ ...absence, staffRef: e.target.value })} /><label>Starts<input required type="datetime-local" style={field} value={absence.startsAt} onChange={e => setAbsence({ ...absence, startsAt: e.target.value })} /></label><label>Ends<input required type="datetime-local" style={field} value={absence.endsAt} onChange={e => setAbsence({ ...absence, endsAt: e.target.value })} /></label><select style={field} value={absence.exceptionType} onChange={e => setAbsence({ ...absence, exceptionType: e.target.value })}><option value="leave">Annual leave</option><option value="sickness">Sickness</option><option value="training">Training</option><option value="restriction">Temporary restriction</option><option value="other">Other</option></select><textarea style={{ ...field, minHeight: 70 }} placeholder="Detail" value={absence.detail} onChange={e => setAbsence({ ...absence, detail: e.target.value })} /><button disabled={busy} style={{ ...button, background: "#b45309" }}>Apply exception</button></form>
    </section>

    <section style={{ ...panel, marginTop: 10 }}><h2 style={{ marginTop: 0 }}>Live coverage assessment</h2><p style={{ color: "#475569" }}>{assessment?.governanceNote}</p>{assessment?.requirements.map(item => <div key={item.requirement.requirementRef} style={{ borderTop: "1px solid #e2e8f0", padding: "10px 0", display: "grid", gap: 4 }}><div><strong>{item.requirement.serviceRef} · {item.requirement.roleRef}</strong> <Badge value={item.status} /></div><div>{item.eligibleCount}/{item.requirement.minimumCount} eligible and rostered · gap {item.gap}</div>{item.excluded?.map((excluded: any) => <small key={`${item.requirement.requirementRef}-${excluded.staffRef}-${excluded.reason}`} style={{ color: "#b91c1c" }}>{excluded.staffRef}: {excluded.reason}</small>)}</div>)}</section>

    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(320px,1fr))", gap: 10, marginTop: 10 }}>
      <div style={panel}><h2 style={{ marginTop: 0 }}>Upcoming shifts</h2>{roster.shifts.length ? roster.shifts.map(item => <div key={item.shiftRef} style={{ borderTop: "1px solid #e2e8f0", padding: "9px 0" }}><div><strong>{item.staffRef}</strong> <Badge value={item.status} /></div><div>{item.departmentRef}{item.areaRef ? ` · ${item.areaRef}` : ""}</div><small>{new Date(item.startsAt).toLocaleString()} → {new Date(item.endsAt).toLocaleString()}</small></div>) : <p>No shifts in the selected window.</p>}</div>
      <div style={panel}><h2 style={{ marginTop: 0 }}>Availability exceptions</h2>{roster.availabilityExceptions.length ? roster.availabilityExceptions.map(item => <div key={item.exceptionRef} style={{ borderTop: "1px solid #e2e8f0", padding: "9px 0" }}><div><strong>{item.staffRef}</strong> <Badge value={item.exceptionType} /></div><small>{new Date(item.startsAt).toLocaleString()} → {new Date(item.endsAt).toLocaleString()}</small><div>{item.detail}</div></div>) : <p>No exceptions recorded.</p>}</div>
    </section>

    <section style={{ ...panel, marginTop: 10 }}><h2 style={{ marginTop: 0 }}>Fatigue and workload signals</h2>{assessment && Object.keys(assessment.staffRisks).length ? Object.entries(assessment.staffRisks).map(([staffRef, risks]) => <div key={staffRef} style={{ borderTop: "1px solid #e2e8f0", padding: "9px 0" }}><strong>{staffRef}</strong>{risks.map((risk, index) => <div key={`${staffRef}-${index}`} style={{ color: risk.severity === "red" ? "#b91c1c" : "#a16207" }}>{risk.type.replaceAll("_", " ")}: {JSON.stringify(risk)}</div>)}</div>) : <p>No configured fatigue or workload signals at this assessment point.</p>}</section>
  </main>;
}
