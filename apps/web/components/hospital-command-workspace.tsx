"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";

const panel: React.CSSProperties = {
  background: "white",
  border: "1px solid #cbd5e1",
  borderRadius: 15,
  padding: 14,
  boxShadow: "0 5px 16px rgba(15,23,42,.05)",
  minWidth: 0,
};
const field: React.CSSProperties = {
  width: "100%",
  minHeight: 46,
  border: "1px solid #94a3b8",
  borderRadius: 9,
  padding: "9px 10px",
  fontSize: 16,
  background: "white",
  color: "#0f172a",
  boxSizing: "border-box",
};
const button: React.CSSProperties = {
  border: 0,
  borderRadius: 9,
  padding: "10px 13px",
  minHeight: 46,
  background: "#0f766e",
  color: "white",
  fontWeight: 850,
  cursor: "pointer",
};
const grid: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,320px),1fr))",
  gap: 9,
};

const EARLY_PHASES = new Set(["referral_received", "intake", "triage", "consult"]);

type CommandView = {
  episode: any;
  referral: any | null;
  consents: any[];
  handovers: any[];
  checkpoints: any[];
  transitions: any[];
  closure: any | null;
  nextTransitions: Record<string, any>;
};

type Tab = "control" | "consent" | "handover" | "closure" | "history";

type Act = (path: string, body: unknown, success: string, method?: string) => Promise<void>;

export function HospitalCommandWorkspace() {
  const [episodeRef, setEpisodeRef] = useState("");
  const [data, setData] = useState<CommandView | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("control");

  const load = useCallback(async () => {
    if (!episodeRef.trim()) return;
    try {
      const result = await apiGet<CommandView>(`/api/v9/episodes/${encodeURIComponent(episodeRef.trim())}/command-view`);
      setData(result);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load canonical episode command view");
    }
  }, [episodeRef]);

  useEffect(() => {
    if (episodeRef.trim()) void load();
  }, [episodeRef, load]);

  const act: Act = async (path, body, success, method = "POST") => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiJson(path, { method, body: JSON.stringify(body) });
      setMessage(success);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Command failed");
    } finally {
      setBusy(false);
    }
  };

  const blockerCount = useMemo(
    () => Object.values(data?.nextTransitions || {}).reduce((total: number, guard: any) => total + (guard.blockers?.length || 0), 0),
    [data],
  );
  const tabs: Array<[Tab, string]> = [
    ["control", "Command"],
    ["consent", "Consent"],
    ["handover", "Handover"],
    ["closure", "Closure"],
    ["history", "History"],
  ];

  return (
    <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
          <div>
            <span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>CANONICAL COMMAND SPINE V9</span>
            <h1 style={{ fontSize: "clamp(36px,8vw,70px)", lineHeight: 0.93, margin: "6px 0" }}>Episode command</h1>
          </div>
          <Link href="/system-control" style={{ color: "white" }}>← System control</Link>
        </div>
        <p style={{ color: "#94a3b8", maxWidth: 900 }}>
          Referral, authority, consent, accountable handover, phase transition and closure all act on the same versioned canonical episode. A transition cannot proceed while its evidence gates are open.
        </p>
        <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
          <input aria-label="Episode reference" placeholder="Canonical episode reference" value={episodeRef} onChange={event => setEpisodeRef(event.target.value)} style={{ ...field, maxWidth: 360 }} />
          <button style={button} onClick={() => void load()}>Load episode</button>
        </div>
      </header>

      <nav aria-label="Episode command sections" style={{ display: "flex", gap: 7, overflowX: "auto", padding: "10px 0" }}>
        {tabs.map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} style={{ ...button, flex: "0 0 auto", background: tab === key ? "#0f766e" : "#334155" }}>{label}</button>
        ))}
      </nav>

      {error && <div aria-live="assertive" style={{ ...panel, borderColor: "#ef4444", color: "#991b1b", marginBottom: 9 }}>{error}</div>}
      {message && <div aria-live="polite" style={{ ...panel, borderColor: "#22c55e", color: "#166534", marginBottom: 9 }}>{message}</div>}

      {!data ? (
        <section style={panel}>Enter a canonical episode reference.</section>
      ) : (
        <>
          <section style={{ ...panel, marginBottom: 9, borderColor: data.episode.status === "closed" ? "#86efac" : blockerCount ? "#f59e0b" : "#93c5fd" }}>
            <small style={{ color: "#64748b", fontWeight: 850 }}>CANONICAL EPISODE</small>
            <h2 style={{ margin: "4px 0" }}>{data.episode.patient_name}</h2>
            <p style={{ margin: 0 }}>{data.episode.episode_ref} · {data.episode.phase} · owner {data.episode.owner_role} · version {data.episode.version}</p>
          </section>
          {tab === "control" && <Control data={data} busy={busy} act={act} />}
          {tab === "consent" && <Consent data={data} busy={busy} act={act} />}
          {tab === "handover" && <Handover data={data} busy={busy} act={act} />}
          {tab === "closure" && <Closure data={data} busy={busy} act={act} />}
          {tab === "history" && <History data={data} />}
        </>
      )}
    </main>
  );
}

function Control({ data, busy, act }: { data: CommandView; busy: boolean; act: Act }) {
  async function decide(status: string) {
    if (!data.referral) return;
    const reason = window.prompt(`Reason for ${status}:`);
    if (!reason) return;
    await act(`/api/v9/referrals/${data.referral.referral_ref}`, { expected_version: data.referral.version, status, reason }, `Referral ${status}.`, "PATCH");
  }

  async function transition(target: string) {
    const reason = window.prompt(`Reason for transition to ${target}:`);
    if (!reason) return;
    await act(
      `/api/v9/episodes/${data.episode.episode_ref}/transition`,
      {
        expected_version: data.episode.version,
        target_phase: target,
        idempotency_key: `ui:${data.episode.episode_ref}:${data.episode.version}:${target}:${Date.now()}`,
        reason,
      },
      `Episode transitioned to ${target}.`,
    );
  }

  async function waive(code: string) {
    const reason = window.prompt(`Senior waiver reason for ${code}:`);
    if (!reason) return;
    const hoursText = window.prompt("Waiver duration in hours, maximum 24:", "1");
    if (!hoursText) return;
    const hours = Number(hoursText);
    if (!Number.isFinite(hours) || hours <= 0 || hours > 24) {
      window.alert("Enter a duration greater than 0 and no more than 24 hours.");
      return;
    }
    await act(
      `/api/v9/episodes/${data.episode.episode_ref}/checkpoints`,
      {
        checkpoint_code: code,
        status: "waived",
        detail: { source: "episode-command-ui", durationHours: hours },
        reason,
        valid_until: new Date(Date.now() + hours * 60 * 60 * 1000).toISOString(),
      },
      `${code} recorded as a time-bounded senior waiver.`,
    );
  }

  return (
    <div style={{ display: "grid", gap: 9 }}>
      <section style={grid}>
        <article style={panel}>
          <small style={{ color: "#64748b", fontWeight: 850 }}>REFERRAL</small>
          <h3>{data.referral?.status || "Missing"}</h3>
          <p>{data.referral?.requested_service} · {data.referral?.urgency}</p>
          {data.referral && data.referral.status !== "accepted" && (
            <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
              <button disabled={busy} style={button} onClick={() => void decide("accepted")}>Accept</button>
              <button disabled={busy} style={{ ...button, background: "#a16207" }} onClick={() => void decide("needs_information")}>Need information</button>
              <button disabled={busy} style={{ ...button, background: "#991b1b" }} onClick={() => void decide("declined")}>Decline</button>
            </div>
          )}
        </article>
        <Metric label="Active consents" value={data.consents.filter(row => row.status === "active").length} />
        <Metric label="Open handovers" value={data.handovers.filter(row => row.status === "offered").length} />
        <Metric label="Current gate failures" value={Object.values(data.nextTransitions).reduce((total: number, guard: any) => total + guard.blockers.length, 0)} />
      </section>

      <section style={{ display: "grid", gap: 8 }}>
        <h2 style={{ marginBottom: 0 }}>Available transitions</h2>
        {Object.entries(data.nextTransitions).map(([target, guard]: [string, any]) => (
          <article key={target} style={{ ...panel, borderColor: guard.canTransition ? "#86efac" : "#ef4444" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "start", flexWrap: "wrap" }}>
              <div>
                <strong style={{ fontSize: 22 }}>{data.episode.phase} → {target}</strong>
                <p style={{ margin: "4px 0" }}>Next accountable role: {guard.targetOwnerRole}</p>
                {guard.earlyClosure && <small>Early referral closure path</small>}
              </div>
              <button disabled={busy || !guard.canTransition} style={{ ...button, background: guard.canTransition ? "#0f766e" : "#94a3b8" }} onClick={() => void transition(target)}>Execute transition</button>
            </div>
            {guard.blockers.map((item: any) => (
              <div key={`${target}-${item.code}`} style={{ marginTop: 7, borderLeft: "5px solid #ef4444", paddingLeft: 9 }}>
                <strong>{item.code}</strong>
                <div>{item.detail}</div>
                {item.waivable === false ? (
                  <small style={{ color: "#991b1b" }}>Structural gate — cannot be waived</small>
                ) : (
                  <button disabled={busy} style={{ ...button, minHeight: 36, padding: "6px 9px", marginTop: 6, background: "#7c3aed" }} onClick={() => void waive(item.code)}>Time-bounded senior waiver</button>
                )}
              </div>
            ))}
            {guard.warnings.map((item: any) => (
              <div key={`${target}-warning-${item.code}`} style={{ marginTop: 7, borderLeft: "5px solid #f59e0b", paddingLeft: 9 }}>
                <strong>{item.code}</strong>
                <div>{item.detail}</div>
                {item.waivedByCheckpoint && <small>Waived by {item.waivedByCheckpoint}</small>}
              </div>
            ))}
          </article>
        ))}
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <article style={panel}>
      <small style={{ color: "#64748b", fontWeight: 850 }}>{label.toUpperCase()}</small>
      <div style={{ fontSize: 34, fontWeight: 950 }}>{value}</div>
    </article>
  );
}

function Consent({ data, busy, act }: { data: CommandView; busy: boolean; act: Act }) {
  const [form, setForm] = useState({ ownerRef: "", type: "admission", decisionMaker: "", channel: "telephone", maximumPounds: "", scope: "{}" });

  async function create() {
    await act(
      `/api/v9/episodes/${data.episode.episode_ref}/consents`,
      {
        owner_ref: form.ownerRef,
        consent_type: form.type,
        scope: JSON.parse(form.scope || "{}"),
        maximum_authorised_pence: form.maximumPounds ? Math.round(Number(form.maximumPounds) * 100) : null,
        currency: "GBP",
        decision_maker_name: form.decisionMaker,
        captured_channel: form.channel,
        reason: "Authority, scope and decision confirmed by verified operator",
      },
      "Consent and authorisation recorded.",
    );
  }

  async function withdraw(row: any) {
    const reason = window.prompt("Withdrawal reason:");
    if (reason) await act(`/api/v9/consents/${row.consent_ref}/withdraw`, { expected_version: row.version, reason }, "Consent withdrawn.", "PATCH");
  }

  return (
    <div style={grid}>
      <section style={{ ...panel, display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0 }}>Record consent</h2>
        <input placeholder="Owner reference" style={field} value={form.ownerRef} onChange={e => setForm({ ...form, ownerRef: e.target.value })} />
        <select style={field} value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}>
          <option value="admission">Admission</option><option value="diagnostics">Diagnostics</option><option value="treatment">Treatment</option><option value="anaesthesia">Anaesthesia</option><option value="procedure">Procedure</option><option value="discharge">Discharge</option>
        </select>
        <input placeholder="Decision maker name" style={field} value={form.decisionMaker} onChange={e => setForm({ ...form, decisionMaker: e.target.value })} />
        <select style={field} value={form.channel} onChange={e => setForm({ ...form, channel: e.target.value })}>
          <option value="in_person">In person</option><option value="telephone">Telephone</option><option value="secure_portal">Secure portal</option><option value="written">Written</option>
        </select>
        <input type="number" step="0.01" placeholder="Maximum authorised amount (£)" style={field} value={form.maximumPounds} onChange={e => setForm({ ...form, maximumPounds: e.target.value })} />
        <small>A financial limit is accepted only when this owner link also carries financial responsibility.</small>
        <textarea aria-label="Consent scope JSON" style={{ ...field, minHeight: 95, fontFamily: "monospace" }} value={form.scope} onChange={e => setForm({ ...form, scope: e.target.value })} />
        <button disabled={busy || !form.ownerRef || !form.decisionMaker} style={button} onClick={() => void create()}>Record consent</button>
      </section>
      <section style={{ display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0 }}>Consent history</h2>
        {data.consents.map(row => (
          <article key={row.consent_ref} style={{ ...panel, borderColor: row.status === "active" ? "#86efac" : "#cbd5e1" }}>
            <strong>{row.consent_type} · {row.status}</strong>
            <p>{row.decision_maker_name} · {row.captured_channel}{row.maximum_authorised_pence != null ? ` · £${(row.maximum_authorised_pence / 100).toFixed(2)}` : ""}</p>
            <button disabled={busy || row.status !== "active"} style={{ ...button, background: "#991b1b" }} onClick={() => void withdraw(row)}>Withdraw</button>
          </article>
        ))}
      </section>
    </div>
  );
}

function Handover({ data, busy, act }: { data: CommandView; busy: boolean; act: Act }) {
  const [form, setForm] = useState({ role: "nurse", subject: "", area: "", priority: "amber", situation: "", background: "", assessment: "", recommendation: "", risks: "[]", actions: "[]" });

  async function create() {
    await act(
      `/api/v9/episodes/${data.episode.episode_ref}/handovers`,
      {
        to_role: form.role,
        to_subject: form.subject || null,
        to_area_ref: form.area || null,
        priority: form.priority,
        situation: form.situation,
        background: form.background,
        assessment: form.assessment,
        recommendation: form.recommendation,
        risks: JSON.parse(form.risks || "[]"),
        pending_actions: JSON.parse(form.actions || "[]"),
        reason: "Structured accountable handover offered",
      },
      "Handover offered.",
    );
  }

  async function acknowledge(row: any) {
    const reason = window.prompt("Acknowledgement note:");
    if (reason) await act(`/api/v9/handovers/${row.handover_ref}/acknowledge`, { expected_version: row.version, reason }, "Handover acknowledged.", "PATCH");
  }

  return (
    <div style={grid}>
      <section style={{ ...panel, display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0 }}>Offer structured handover</h2>
        <select style={field} value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>
          <option value="nurse">Nurse</option><option value="clinician">Clinician</option><option value="ops_manager">Operations manager</option><option value="admin">Administration</option><option value="senior_clinician">Senior clinician</option>
        </select>
        <input placeholder="Receiving subject, optional" style={field} value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} />
        <input placeholder="Receiving area" style={field} value={form.area} onChange={e => setForm({ ...form, area: e.target.value })} />
        <select style={field} value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })}><option>green</option><option>amber</option><option>red</option></select>
        <textarea placeholder="Situation" style={{ ...field, minHeight: 75 }} value={form.situation} onChange={e => setForm({ ...form, situation: e.target.value })} />
        <textarea placeholder="Background" style={{ ...field, minHeight: 75 }} value={form.background} onChange={e => setForm({ ...form, background: e.target.value })} />
        <textarea placeholder="Assessment" style={{ ...field, minHeight: 75 }} value={form.assessment} onChange={e => setForm({ ...form, assessment: e.target.value })} />
        <textarea placeholder="Recommendation" style={{ ...field, minHeight: 75 }} value={form.recommendation} onChange={e => setForm({ ...form, recommendation: e.target.value })} />
        <textarea aria-label="Handover risks JSON" style={{ ...field, minHeight: 80, fontFamily: "monospace" }} value={form.risks} onChange={e => setForm({ ...form, risks: e.target.value })} />
        <textarea aria-label="Pending actions JSON" style={{ ...field, minHeight: 80, fontFamily: "monospace" }} value={form.actions} onChange={e => setForm({ ...form, actions: e.target.value })} />
        <button disabled={busy || !form.situation} style={button} onClick={() => void create()}>Offer handover</button>
      </section>
      <section style={{ display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0 }}>Handover ledger</h2>
        {data.handovers.map(row => (
          <article key={row.handover_ref} style={{ ...panel, borderColor: row.status === "offered" ? "#f59e0b" : "#86efac" }}>
            <strong>{row.from_role} → {row.to_role} · {row.status}</strong>
            <p>{row.situation}</p>
            <small>{row.pending_actions.length} pending actions · {row.risks.length} risks</small>
            <div><button disabled={busy || row.status !== "offered"} style={button} onClick={() => void acknowledge(row)}>Acknowledge</button></div>
          </article>
        ))}
      </section>
    </div>
  );
}

function Closure({ data, busy, act }: { data: CommandView; busy: boolean; act: Act }) {
  const early = EARLY_PHASES.has(data.episode.phase);
  const [form, setForm] = useState({
    disposition: early ? "referral_declined" : "discharged_home",
    documentRef: "",
    ownerCommRef: "",
    referrerCommRef: "",
    estimateRef: "",
    financialStatus: early ? "no_charge" : "settled",
    retainedRisks: "[]",
  });

  async function prepare() {
    await act(
      `/api/v9/episodes/${data.episode.episode_ref}/closure`,
      {
        disposition: form.disposition,
        discharge_document_ref: form.documentRef || null,
        owner_communication_ref: form.ownerCommRef || null,
        referrer_communication_ref: form.referrerCommRef || null,
        final_estimate_ref: form.estimateRef || null,
        financial_status: form.financialStatus,
        outstanding_actions: [],
        retained_risks: JSON.parse(form.retainedRisks || "[]"),
        reason: early ? "Early referral closure prepared from decision and communication evidence" : "Episode closure record prepared from verified discharge evidence",
      },
      "Closure record prepared.",
    );
  }

  async function approve() {
    if (!data.closure) return;
    const reason = window.prompt("Senior approval reason:");
    if (reason) await act(`/api/v9/closures/${data.closure.closure_ref}/approve`, { expected_version: data.closure.version, reason }, "Closure approved.", "PATCH");
  }

  const evidenceReady = early ? Boolean(form.ownerCommRef || form.referrerCommRef) : Boolean(form.documentRef && form.ownerCommRef);

  return (
    <div style={grid}>
      <section style={{ ...panel, display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0 }}>{early ? "Prepare referral closure" : "Prepare clinical closure"}</h2>
        {early && <p style={{ margin: 0 }}>This case has not reached discharge. The closure records the referral decision and communication without creating false discharge evidence.</p>}
        <select style={field} value={form.disposition} onChange={e => setForm({ ...form, disposition: e.target.value })}>
          {early ? <><option value="referral_declined">Referral declined</option><option value="referral_cancelled">Referral cancelled</option><option value="not_attended">Not attended</option></> : <><option value="discharged_home">Discharged home</option><option value="transferred">Transferred</option><option value="deceased">Deceased</option><option value="euthanised">Euthanised</option></>}
        </select>
        {!early && <input placeholder="Sent discharge document reference" style={field} value={form.documentRef} onChange={e => setForm({ ...form, documentRef: e.target.value })} />}
        <input placeholder={early ? "Owner communication reference, optional if referrer recorded" : "Owner communication reference"} style={field} value={form.ownerCommRef} onChange={e => setForm({ ...form, ownerCommRef: e.target.value })} />
        <input placeholder={early ? "Referrer communication reference, optional if owner recorded" : "Referrer communication reference"} style={field} value={form.referrerCommRef} onChange={e => setForm({ ...form, referrerCommRef: e.target.value })} />
        <input placeholder="Final approved estimate reference, optional" style={field} value={form.estimateRef} onChange={e => setForm({ ...form, estimateRef: e.target.value })} />
        <select style={field} value={form.financialStatus} onChange={e => setForm({ ...form, financialStatus: e.target.value })}>
          <option value="settled">Settled</option><option value="insured_pending">Insurance pending</option><option value="transferred">Transferred</option><option value="written_off">Written off</option><option value="no_charge">No charge</option>
        </select>
        <textarea aria-label="Retained risks JSON" style={{ ...field, minHeight: 90, fontFamily: "monospace" }} value={form.retainedRisks} onChange={e => setForm({ ...form, retainedRisks: e.target.value })} />
        <button disabled={busy || Boolean(data.closure) || !evidenceReady} style={button} onClick={() => void prepare()}>Prepare closure</button>
      </section>
      <section style={panel}>
        <h2 style={{ marginTop: 0 }}>Closure status</h2>
        {!data.closure ? <p>No closure record.</p> : <>
          <strong>{data.closure.status}</strong>
          <p>{data.closure.disposition} · financial status {data.closure.financial_status} · version {data.closure.version}</p>
          <p>{data.closure.outstanding_actions.length} outstanding actions · {data.closure.retained_risks.length} retained risks</p>
          <button disabled={busy || data.closure.status !== "draft"} style={button} onClick={() => void approve()}>Senior approve</button>
        </>}
      </section>
    </div>
  );
}

function History({ data }: { data: CommandView }) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <section style={panel}>
        <h2 style={{ marginTop: 0 }}>Checkpoints and waivers</h2>
        {data.checkpoints.length ? data.checkpoints.map(row => (
          <article key={row.checkpoint_ref} style={{ borderTop: "1px solid #e2e8f0", padding: "9px 0" }}>
            <strong>{row.checkpoint_code} · {row.status}</strong>
            <div>{row.reason}</div>
            {row.valid_until && <small>Expires {new Date(row.valid_until).toLocaleString()}</small>}
          </article>
        )) : <p>No checkpoints.</p>}
      </section>
      <section style={panel}>
        <h2 style={{ marginTop: 0 }}>Transition ledger</h2>
        {data.transitions.map(row => (
          <article key={row.transition_ref} style={{ borderTop: "1px solid #e2e8f0", padding: "9px 0" }}>
            <strong>{row.from_phase} → {row.to_phase} · {row.status}</strong>
            <div>{row.actor_role} · {row.reason}</div>
            <small>{row.blockers.length} blockers · {row.warnings.length} warnings · {new Date(row.created_at).toLocaleString()}</small>
          </article>
        ))}
      </section>
    </div>
  );
}
