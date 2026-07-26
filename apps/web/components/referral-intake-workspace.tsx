"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 14, boxShadow: "0 5px 16px rgba(15,23,42,.05)" };
const field: React.CSSProperties = { width: "100%", minHeight: 46, border: "1px solid #94a3b8", borderRadius: 9, padding: "9px 10px", fontSize: 16, background: "white", color: "#0f172a", boxSizing: "border-box" };
const button: React.CSSProperties = { border: 0, borderRadius: 9, padding: "10px 13px", minHeight: 46, background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };

export function ReferralIntakeWorkspace() {
  const [items, setItems] = useState<any[]>([]);
  const [filter, setFilter] = useState({ status: "", urgency: "", service: "" });
  const [form, setForm] = useState({
    patientRef: "",
    premisesRef: "bvs-bristol",
    sourceType: "referring_vet",
    organisation: "",
    contactName: "",
    contactEmail: "",
    contactPhone: "",
    service: "",
    problem: "",
    summary: "",
    urgency: "routine",
    timeframe: "",
  });
  const [created, setCreated] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    if (filter.status) params.set("status", filter.status);
    if (filter.urgency) params.set("urgency", filter.urgency);
    if (filter.service) params.set("requested_service", filter.service);
    try {
      const result = await apiGet<{ items: any[] }>(`/api/v9/referrals${params.size ? `?${params.toString()}` : ""}`);
      setItems(result.items);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load referral queue");
    }
  }, [filter]);

  useEffect(() => { void load(); }, [load]);

  async function createReferral() {
    setBusy(true);
    setError("");
    setCreated(null);
    try {
      const result = await apiJson<any>("/api/v9/referrals", {
        method: "POST",
        body: JSON.stringify({
          patient_ref: form.patientRef,
          premises_ref: form.premisesRef,
          source_type: form.sourceType,
          source_organisation: form.organisation || null,
          source_contact_name: form.contactName || null,
          source_contact_email: form.contactEmail || null,
          source_contact_phone: form.contactPhone || null,
          requested_service: form.service,
          presenting_problem: form.problem,
          clinical_summary: form.summary,
          urgency: form.urgency,
          requested_timeframe: form.timeframe || null,
          attachments: [],
          reason: "Referral identity, source and presenting information recorded by verified intake operator",
        }),
      });
      setCreated(result);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create referral");
    } finally {
      setBusy(false);
    }
  }

  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div><span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>CANONICAL REFERRAL INTAKE V9</span><h1 style={{ fontSize: "clamp(36px,8vw,70px)", lineHeight: .93, margin: "6px 0" }}>Referral worklist</h1></div>
        <Link href="/system-control" style={{ color: "white" }}>← System control</Link>
      </div>
      <p style={{ color: "#94a3b8", maxWidth: 900 }}>Reception and referral teams create the canonical episode once, with patient identity and source provenance. Clinical acceptance and all later phase changes occur in Episode command.</p>
    </header>

    {error && <div aria-live="assertive" style={{ ...panel, borderColor: "#ef4444", color: "#991b1b", marginTop: 9 }}>{error}</div>}
    {created && <section style={{ ...panel, marginTop: 9, borderColor: "#22c55e" }}><strong>Referral created</strong><p>{created.referral.referral_ref} · episode {created.episode.episode_ref}</p><Link href={`/episode-command?episode=${encodeURIComponent(created.episode.episode_ref)}`}>Open canonical episode command →</Link></section>}

    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,350px),1fr))", gap: 10, marginTop: 10 }}>
      <article style={{ ...panel, display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0 }}>Create referral</h2>
        <input placeholder="Existing patient reference" style={field} value={form.patientRef} onChange={e => setForm({ ...form, patientRef: e.target.value })} />
        <input placeholder="Premises reference" style={field} value={form.premisesRef} onChange={e => setForm({ ...form, premisesRef: e.target.value })} />
        <select style={field} value={form.sourceType} onChange={e => setForm({ ...form, sourceType: e.target.value })}><option value="referring_vet">Referring vet</option><option value="owner">Owner</option><option value="internal_transfer">Internal transfer</option><option value="emergency">Emergency presentation</option></select>
        <input placeholder="Source organisation" style={field} value={form.organisation} onChange={e => setForm({ ...form, organisation: e.target.value })} />
        <input placeholder="Source contact name" style={field} value={form.contactName} onChange={e => setForm({ ...form, contactName: e.target.value })} />
        <input type="email" placeholder="Source email" style={field} value={form.contactEmail} onChange={e => setForm({ ...form, contactEmail: e.target.value })} />
        <input placeholder="Source telephone" style={field} value={form.contactPhone} onChange={e => setForm({ ...form, contactPhone: e.target.value })} />
        <input placeholder="Requested service" style={field} value={form.service} onChange={e => setForm({ ...form, service: e.target.value })} />
        <textarea placeholder="Presenting problem" style={{ ...field, minHeight: 80 }} value={form.problem} onChange={e => setForm({ ...form, problem: e.target.value })} />
        <textarea placeholder="Clinical summary" style={{ ...field, minHeight: 100 }} value={form.summary} onChange={e => setForm({ ...form, summary: e.target.value })} />
        <select style={field} value={form.urgency} onChange={e => setForm({ ...form, urgency: e.target.value })}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option><option value="red">Red</option></select>
        <input placeholder="Requested timeframe" style={field} value={form.timeframe} onChange={e => setForm({ ...form, timeframe: e.target.value })} />
        <button disabled={busy || !form.patientRef || !form.service || !form.problem} style={button} onClick={() => void createReferral()}>Create canonical referral</button>
      </article>

      <article style={{ display: "grid", gap: 8, alignContent: "start" }}>
        <section style={{ ...panel, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))", gap: 7 }}>
          <select aria-label="Referral status filter" style={field} value={filter.status} onChange={e => setFilter({ ...filter, status: e.target.value })}><option value="">All statuses</option><option value="received">Received</option><option value="accepted">Accepted</option><option value="needs_information">Needs information</option><option value="declined">Declined</option></select>
          <select aria-label="Referral urgency filter" style={field} value={filter.urgency} onChange={e => setFilter({ ...filter, urgency: e.target.value })}><option value="">All urgency</option><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option><option value="red">Red</option></select>
          <input aria-label="Requested service filter" placeholder="Service filter" style={field} value={filter.service} onChange={e => setFilter({ ...filter, service: e.target.value })} />
        </section>
        <h2 style={{ margin: "4px 0" }}>{items.length} referrals</h2>
        {items.map(row => <section key={row.referral_ref} style={{ ...panel, borderColor: row.urgency === "red" || row.urgency === "emergency" ? "#ef4444" : row.status === "needs_information" ? "#f59e0b" : "#cbd5e1" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><strong style={{ fontSize: 20 }}>{row.patientName || row.patient_ref}</strong><b>{row.urgency}</b></div>
          <p>{row.requested_service} · {row.status} · phase {row.episodePhase}</p>
          <p>{row.presenting_problem}</p>
          <small>{row.source_organisation || row.source_type} · received {new Date(row.received_at).toLocaleString()}</small>
          <div style={{ marginTop: 8 }}><Link href={`/episode-command?episode=${encodeURIComponent(row.episode_ref)}`}>Open episode command →</Link></div>
        </section>)}
      </article>
    </section>
  </main>;
}
