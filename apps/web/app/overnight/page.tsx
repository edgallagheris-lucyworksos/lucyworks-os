"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type OvernightBoard = {
  summary: Record<string, number>;
  room_groups: any[];
};

type OvernightGrid = {
  basis: string;
  slots: any[];
};

function fmt(value?: string | null) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return value;
  }
}

function riskBorder(risk?: string) {
  if (risk === "red") return "1px solid #7f1d1d";
  if (risk === "amber") return "1px solid #78350f";
  return "1px solid #14532d";
}

function riskBg(risk?: string) {
  if (risk === "red") return "rgba(127, 29, 29, 0.24)";
  if (risk === "amber") return "rgba(120, 53, 15, 0.22)";
  return "rgba(20, 83, 45, 0.16)";
}

function OvernightInner() {
  const [board, setBoard] = useState<OvernightBoard | null>(null);
  const [grid, setGrid] = useState<OvernightGrid | null>(null);
  const [selected, setSelected] = useState<any | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [boardRes, gridRes] = await Promise.all([
        fetch(`${API_BASE}/api/overnight-board`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/overnight-grid`, { cache: "no-store" }),
      ]);
      if (!boardRes.ok) throw new Error(`overnight-board ${boardRes.status}`);
      if (!gridRes.ok) throw new Error(`overnight-grid ${gridRes.status}`);
      setBoard(await boardRes.json());
      setGrid(await gridRes.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Overnight board failed to load");
    }
  }

  async function seedHospitalScale() {
    setStatus("Loading hospital-scale demo...");
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/admin/seed-hospital-scale`, { method: "POST" });
      if (!res.ok) throw new Error(`seed failed ${res.status}`);
      await load();
      setStatus("Hospital-scale demo loaded: theatres, MRI/CT/X-ray, ICU/wards, pharmacy, insurance, overnight tasks.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hospital-scale seed failed");
      setStatus("");
    }
  }

  useEffect(() => { load(); }, []);

  const rooms = useMemo(() => board?.room_groups || [], [board]);
  const gridSlots = grid?.slots || [];

  return (
    <HospitalShell title="Overnight / Inpatient Command" subtitle="Ward and ICU carry-over, night handover, medication, observations, insurance and morning review">
      <div style={{ display: "grid", gap: 16 }}>
        <section className="lw-card" style={{ padding: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Day + night continuity</div>
              <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.04em" }}>Patients do not disappear after theatre</h1>
              <p style={{ color: "#94a3b8", marginBottom: 0 }}>Active inpatients, overnight obs, meds due, handovers, ICU/ward load, pharmacy and insurance blockers.</p>
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button className="lw-pill lw-btn-primary" onClick={seedHospitalScale}>Load hospital-scale demo</button>
              <button className="lw-pill" onClick={load}>Refresh</button>
              <Link href="/dashboard" className="lw-pill">Dashboard</Link>
            </div>
          </div>
          {status ? <p style={{ color: "#2dd4bf" }}>{status}</p> : null}
          {error ? <p style={{ color: "#fca5a5" }}>{error}</p> : null}
        </section>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
          {[
            ["Active inpatients", board?.summary?.active_inpatients ?? 0],
            ["ICU / HD", board?.summary?.icu_or_high_dependency ?? 0],
            ["Overnight required", board?.summary?.overnight_required ?? 0],
            ["Unack handovers", board?.summary?.unacknowledged_handovers ?? 0],
            ["Open overnight work", board?.summary?.open_overnight_work ?? 0],
            ["Finance / insurance blocks", board?.summary?.finance_or_insurance_blocks ?? 0],
            ["Rooms tracked", board?.summary?.rooms_tracked ?? 0],
          ].map(([label, value]) => (
            <div key={String(label)} className="lw-card" style={{ padding: 16 }}>
              <div style={{ color: "#94a3b8" }}>{label}</div>
              <div style={{ fontSize: 30, fontWeight: 950 }}>{String(value)}</div>
            </div>
          ))}
        </section>

        <section className="lw-card" style={{ overflow: "hidden" }}>
          <div style={{ padding: 14, borderBottom: "1px solid #1f2937", display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <strong>19:00–07:00 15-minute overnight grid</strong>
            <span style={{ color: "#94a3b8" }}>Obs and medication due blocks from inpatient stays.</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <div style={{ minWidth: 960, display: "grid", gridTemplateColumns: "110px 1fr 1fr 90px" }}>
              <div style={{ padding: 10, borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>Time</div>
              <div style={{ padding: 10, borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>Observations</div>
              <div style={{ padding: 10, borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>Medication</div>
              <div style={{ padding: 10, borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>Risk</div>
              {gridSlots.map((slot) => (
                <div key={slot.slot_index} style={{ display: "contents" }}>
                  <button onClick={() => setSelected({ type: "slot", slot })} style={{ textAlign: "left", padding: 10, border: 0, borderBottom: "1px solid #1f2937", background: riskBg(slot.risk), color: "#f8fafc" }}>
                    <strong>{fmt(slot.starts_at)}</strong>
                    <div style={{ color: "#94a3b8", fontSize: 11 }}>{fmt(slot.ends_at)}</div>
                  </button>
                  <div style={{ padding: 10, borderBottom: "1px solid #1f2937" }}>
                    {(slot.observation_tasks || []).map((task: any) => <button key={`obs-${task.id}`} onClick={() => setSelected({ type: "obs", item: task })} className="lw-pill" style={{ margin: 3 }}>{task.task_type} • EP-{task.episode_id}</button>)}
                  </div>
                  <div style={{ padding: 10, borderBottom: "1px solid #1f2937" }}>
                    {(slot.medications_due || []).map((med: any) => <button key={`med-${med.id}`} onClick={() => setSelected({ type: "med", item: med })} className="lw-pill" style={{ margin: 3 }}>{med.medication_name} • EP-{med.episode_id}</button>)}
                  </div>
                  <div style={{ padding: 10, borderBottom: "1px solid #1f2937", color: slot.risk === "red" ? "#fca5a5" : slot.risk === "amber" ? "#fbbf24" : "#86efac" }}>{slot.risk}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section>
          <h2>Ward / ICU room groups</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 14 }}>
            {rooms.map((group) => (
              <article key={group.room_name} className="lw-card" style={{ padding: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                  <strong>{group.room_name}</strong>
                  <span style={{ color: "#94a3b8" }}>active {group.active} • red {group.red} • amber {group.amber}</span>
                </div>
                <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
                  {(group.cards || []).map((card: any) => (
                    <button key={card.stay?.id} onClick={() => setSelected({ type: "inpatient", item: card })} style={{ textAlign: "left", border: riskBorder(card.risk), borderRadius: 14, padding: 12, background: riskBg(card.risk) }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                        <strong>{card.patient?.name || "Unknown"} • {card.episode?.episode_ref}</strong>
                        <span>{card.risk?.toUpperCase()}</span>
                      </div>
                      <div style={{ color: "#94a3b8", marginTop: 6 }}>{card.stay?.bed_label} • {card.stay?.acuity} • obs every {card.stay?.obs_frequency_minutes} min</div>
                      <div style={{ marginTop: 8 }}>{card.next_action || "No immediate next action"}</div>
                      {card.financial_consent_status ? <div style={{ color: "#fbbf24", marginTop: 8 }}>Insurance {card.financial_consent_status.insurance_status} • payment {card.financial_consent_status.payment_status}</div> : null}
                    </button>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="lw-card" style={{ padding: 16 }}>
          <h2 style={{ marginTop: 0 }}>Selected overnight object</h2>
          {!selected ? <p style={{ color: "#94a3b8" }}>Select an inpatient, observation, medication or 15-minute slot.</p> : null}
          {selected?.type === "inpatient" ? (
            <div style={{ display: "grid", gap: 10 }}>
              <strong>{selected.item.patient?.name} • {selected.item.episode?.episode_ref} • {selected.item.risk}</strong>
              <div style={{ color: "#94a3b8" }}>Location {selected.item.stay?.location_room} / {selected.item.stay?.bed_label} • acuity {selected.item.stay?.acuity}</div>
              <div>{selected.item.next_action || "No next action"}</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                <div className="lw-card" style={{ padding: 12 }}><strong>Observations</strong>{(selected.item.observation_tasks || []).map((x: any) => <div key={x.id} style={{ color: "#94a3b8", marginTop: 6 }}>{fmt(x.due_at)} • {x.task_type} • {x.status}</div>)}</div>
                <div className="lw-card" style={{ padding: 12 }}><strong>Medications</strong>{(selected.item.medications_due || []).map((x: any) => <div key={x.id} style={{ color: "#94a3b8", marginTop: 6 }}>{fmt(x.due_at)} • {x.medication_name} • {x.status}</div>)}</div>
                <div className="lw-card" style={{ padding: 12 }}><strong>Handovers</strong>{(selected.item.handovers || []).map((x: any) => <div key={x.id} style={{ color: "#94a3b8", marginTop: 6 }}>{x.risk_level} • {x.acknowledged ? "acknowledged" : "not acknowledged"} • {x.summary}</div>)}</div>
                <div className="lw-card" style={{ padding: 12 }}><strong>Finance / insurance</strong>{selected.item.financial_consent_status ? <div style={{ color: "#94a3b8", marginTop: 6 }}>Consent {selected.item.financial_consent_status.consent_status}<br />Estimate {selected.item.financial_consent_status.estimate_status}<br />Insurance {selected.item.financial_consent_status.insurance_status}<br />Payment {selected.item.financial_consent_status.payment_status}<br />Pharmacy blocked {String(selected.item.financial_consent_status.pharmacy_blocked)}<br />Discharge blocked {String(selected.item.financial_consent_status.discharge_blocked)}</div> : <div style={{ color: "#94a3b8" }}>No finance row.</div>}</div>
              </div>
            </div>
          ) : selected ? <pre style={{ overflow: "auto", whiteSpace: "pre-wrap", color: "#cbd5e1" }}>{JSON.stringify(selected, null, 2)}</pre> : null}
        </section>
      </div>
    </HospitalShell>
  );
}

export default function OvernightPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>{() => <OvernightInner />}</AuthGuard>;
}
