"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";

type Complaint = {
  complaint_ref: string;
  channel: string;
  category: string;
  severity: string;
  summary: string;
  assigned_role: string;
  assigned_subject?: string;
  due_at?: string;
  status: string;
  resolution?: string;
  version: number;
  created_at: string;
};

type Snapshot = { complaints: Complaint[] };
type Identity = { user: { role: string } };

const MANAGER_ROLES = new Set(["admin", "ops_manager", "hospital_director", "governance_lead", "clinical_director"]);

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

export function EpisodeComplaintControl() {
  const [episodeRef, setEpisodeRef] = useState("");
  const [items, setItems] = useState<Complaint[]>([]);
  const [role, setRole] = useState("");
  const [resolution, setResolution] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    const read = () => setEpisodeRef(new URLSearchParams(window.location.search).get("episode") || "");
    read();
    window.addEventListener("popstate", read);
    return () => window.removeEventListener("popstate", read);
  }, []);

  const refresh = useCallback(async () => {
    if (!episodeRef) return;
    try {
      const [snapshot, identity] = await Promise.all([
        apiGet<Snapshot>(`/api/v32/episodes/${encodeURIComponent(episodeRef)}/governance`),
        apiGet<Identity>("/api/auth/me"),
      ]);
      setItems(snapshot.complaints || []);
      setRole(identity.user.role || "");
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Complaint status unavailable");
    }
  }, [episodeRef]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 20_000);
    const onUpdate = () => void refresh();
    window.addEventListener("lucyworks:episode-updated", onUpdate);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("lucyworks:episode-updated", onUpdate);
    };
  }, [refresh]);

  const open = useMemo(() => items.filter(item => !["resolved", "closed"].includes(item.status)), [items]);
  const canManage = MANAGER_ROLES.has(role);

  async function update(item: Complaint, status: string) {
    const value = (resolution[item.complaint_ref] || "").trim();
    if (["resolved", "closed"].includes(status) && !value) {
      setError("Record the complaint resolution before resolving or closing it.");
      return;
    }
    setBusy(item.complaint_ref);
    setError("");
    setMessage("");
    try {
      await apiJson(`/api/v32/complaints/${encodeURIComponent(item.complaint_ref)}`, {
        method: "PATCH",
        body: JSON.stringify({
          expectedVersion: item.version,
          status,
          resolution: value || undefined,
          reason: `Complaint moved to ${status} from episode complaint control`,
        }),
      });
      setMessage(`Complaint ${label(status).toLowerCase()}.`);
      await refresh();
      window.dispatchEvent(new Event("lucyworks:episode-updated"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Complaint update failed");
      await refresh();
    } finally {
      setBusy("");
    }
  }

  if (!episodeRef || !items.length) return null;

  return (
    <section className="ecc" aria-label="Complaint control">
      <style>{css}</style>
      <header>
        <div><span>Client recovery</span><h2>Complaint ownership & resolution</h2></div>
        <strong>{open.length} open</strong>
      </header>
      {error ? <div className="alert error" role="alert">{error}</div> : null}
      {message ? <div className="alert success" role="status">{message}</div> : null}
      <div className="list">
        {items.map(item => (
          <article key={item.complaint_ref} className={["resolved", "closed"].includes(item.status) ? "closed" : item.severity === "critical" || item.severity === "serious" ? "risk" : "open"}>
            <div className="meta"><span>{label(item.category)} · {label(item.channel)}</span><strong>{label(item.status)}</strong></div>
            <h3>{item.summary}</h3>
            <dl><div><dt>Owner</dt><dd>{label(item.assigned_role)}{item.assigned_subject ? ` · ${item.assigned_subject}` : ""}</dd></div><div><dt>Due</dt><dd>{item.due_at ? new Date(item.due_at).toLocaleString() : "Not set"}</dd></div><div><dt>Severity</dt><dd>{label(item.severity)}</dd></div><div><dt>Version</dt><dd>{item.version}</dd></div></dl>
            {item.resolution ? <p className="resolution"><b>Resolution:</b> {item.resolution}</p> : null}
            {canManage && !["resolved", "closed"].includes(item.status) ? <div className="actions">
              <textarea value={resolution[item.complaint_ref] || ""} onChange={event => setResolution(current => ({ ...current, [item.complaint_ref]: event.target.value }))} placeholder="Investigation note or final resolution" />
              <div><button disabled={busy === item.complaint_ref} onClick={() => void update(item, "acknowledged")}>Acknowledge</button><button disabled={busy === item.complaint_ref} onClick={() => void update(item, "investigating")}>Investigating</button><button className="resolve" disabled={busy === item.complaint_ref} onClick={() => void update(item, "resolved")}>Resolve</button></div>
            </div> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

const css = `
.ecc{margin:0 12px 14px;background:#fff;border:1px solid #d7dee8;border-radius:14px;box-shadow:0 5px 18px rgba(15,23,42,.05);overflow:hidden;color:#172033;font-family:Inter,system-ui,sans-serif}.ecc *{box-sizing:border-box}.ecc>header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 14px;background:#f8fafc;border-bottom:1px solid #e4e9ef}.ecc header span{display:block;color:#65758a;font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.ecc h2{margin:2px 0 0;font-size:17px}.ecc>header>strong{padding:6px 9px;border-radius:999px;background:#fff7ed;color:#9a5213;font-size:11px}.list{display:grid;gap:8px;padding:12px 14px}.list article{border:1px solid #dfe6ed;border-left:4px solid #d18a16;border-radius:9px;padding:11px}.list article.risk{border-left-color:#c2413b}.list article.closed{border-left-color:#27855f;background:#f8fcfa}.meta{display:flex;justify-content:space-between;gap:8px;color:#69788b;font-size:10px;font-weight:750}.meta strong{color:#324960}.list h3{margin:6px 0;font-size:14px;line-height:1.35}.list dl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:8px 0 0}.list dl div{background:#f8fafc;border-radius:7px;padding:7px}.list dt{color:#718096;font-size:9px;font-weight:800;text-transform:uppercase}.list dd{margin:2px 0 0;font-size:11px;font-weight:700}.resolution{margin:8px 0 0;padding:8px;border-radius:7px;background:#f2fbf6;color:#355a47;font-size:11px}.actions{display:grid;gap:7px;margin-top:9px}.actions textarea{width:100%;min-height:65px;border:1px solid #b8c4d1;border-radius:8px;padding:8px;color:#172033;background:white}.actions>div{display:flex;gap:6px;flex-wrap:wrap}.actions button{border:1px solid #c6d1dc;border-radius:7px;background:#f8fafc;color:#294761;padding:8px 10px;font-weight:800;cursor:pointer}.actions button.resolve{border-color:#27855f;background:#27855f;color:white}.actions button:disabled{opacity:.5}.alert{margin:9px 14px 0;border-radius:8px;padding:8px 10px;font-size:11px;font-weight:700}.alert.error{background:#fff1f2;color:#991b1b}.alert.success{background:#f0fdf4;color:#166534}
@media(max-width:760px){.ecc{margin:0 7px 10px}.list dl{grid-template-columns:1fr 1fr}}
`;