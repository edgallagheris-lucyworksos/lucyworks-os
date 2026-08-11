"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";

type Blocker = { code: string; severity: string; message: string };
type Snapshot = {
  episode: { episodeRef: string; patientRef?: string; phase: string; status: string };
  summary: {
    estimateVersions: number;
    charges: number;
    chargeTotalPence: number;
    prescriptionChoices: number;
    openComplaints: number;
    unreviewedAI: number;
    blockers: number;
  };
  blockers: Blocker[];
  latestEstimate?: {
    current_upper_total_pence: number;
    written_estimate_required: boolean;
    written_update_required: boolean;
    written_delivery_ref?: string;
    status: string;
  } | null;
};

function money(pence: number) {
  return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(pence / 100);
}

export function EpisodeGovernancePanel() {
  const [episodeRef, setEpisodeRef] = useState("");
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState("Waiting for episode");

  useEffect(() => {
    const read = () => setEpisodeRef(new URLSearchParams(window.location.search).get("episode") || "");
    read();
    window.addEventListener("popstate", read);
    const timer = window.setInterval(read, 1500);
    return () => {
      window.removeEventListener("popstate", read);
      window.clearInterval(timer);
    };
  }, []);

  const refresh = useCallback(async () => {
    if (!episodeRef) {
      setSnapshot(null);
      return;
    }
    try {
      const data = await apiGet<Snapshot>(`/api/v32/episodes/${encodeURIComponent(episodeRef)}/governance`);
      setSnapshot(data);
      setStatus(`Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Governance status unavailable");
    }
  }, [episodeRef]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    const onUpdate = () => void refresh();
    window.addEventListener("lucyworks:episode-updated", onUpdate);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("lucyworks:episode-updated", onUpdate);
    };
  }, [refresh]);

  const finance = useMemo(() => {
    if (!snapshot?.latestEstimate) return null;
    const estimate = snapshot.latestEstimate.current_upper_total_pence;
    const charges = snapshot.summary.chargeTotalPence;
    return { estimate, charges, remaining: estimate - charges, over: charges > estimate };
  }, [snapshot]);

  if (!episodeRef) return null;

  return (
    <section className="egp" aria-label="Episode assurance">
      <style>{css}</style>
      <header>
        <div>
          <span>Operational assurance</span>
          <h2>Evidence, client & financial controls</h2>
        </div>
        <button type="button" onClick={() => void refresh()}>Refresh</button>
      </header>

      {!snapshot ? <p className="egp-status">{status}</p> : <>
        <div className="egp-metrics">
          <article><strong>{snapshot.summary.blockers}</strong><span>open blockers</span></article>
          <article><strong>{snapshot.summary.openComplaints}</strong><span>client complaints</span></article>
          <article><strong>{snapshot.summary.unreviewedAI}</strong><span>AI drafts to review</span></article>
          <article><strong>{snapshot.summary.prescriptionChoices}</strong><span>prescription decisions</span></article>
          <article><strong>{money(snapshot.summary.chargeTotalPence)}</strong><span>recorded charges</span></article>
          <article className={finance?.over ? "metric-risk" : ""}><strong>{finance ? money(finance.remaining) : "—"}</strong><span>{finance?.over ? "over estimate ceiling" : "estimate headroom"}</span></article>
        </div>

        {finance ? <div className={`egp-finance ${finance.over ? "risk" : "clear"}`}>
          <div><small>Latest estimate ceiling</small><strong>{money(finance.estimate)}</strong></div>
          <div><small>Recorded charges</small><strong>{money(finance.charges)}</strong></div>
          <div><small>{finance.over ? "Uncovered variance" : "Remaining headroom"}</small><strong>{money(Math.abs(finance.remaining))}</strong></div>
          <p>{finance.over ? "Charges have moved beyond the latest recorded estimate ceiling. Client communication and estimate-update evidence require review." : "Charges remain within the latest recorded estimate ceiling. Continue reconciling legitimate charges as care changes."}</p>
        </div> : null}

        {snapshot.blockers.length ? (
          <div className="egp-blockers">
            {snapshot.blockers.map(blocker => (
              <div key={blocker.code} className={blocker.severity === "red" ? "red" : "amber"}>
                <strong>{blocker.code.replaceAll("_", " ")}</strong>
                <span>{blocker.message}</span>
              </div>
            ))}
          </div>
        ) : <div className="egp-clear"><strong>No governance blockers recorded.</strong><span>Current regulated evidence checks are clear.</span></div>}

        <footer>
          <span>{status}</span>
          {snapshot.latestEstimate ? <strong>Latest estimate ceiling {money(snapshot.latestEstimate.current_upper_total_pence)}</strong> : <strong>No regulated estimate recorded</strong>}
        </footer>
      </>}
    </section>
  );
}

const css = `
.egp{margin:0 12px 14px;background:#fff;border:1px solid #d7dee8;border-radius:14px;box-shadow:0 5px 18px rgba(15,23,42,.05);color:#172033;font-family:Inter,system-ui,sans-serif;overflow:hidden}.egp *{box-sizing:border-box}.egp>header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:13px 15px;border-bottom:1px solid #e4e9ef;background:#f8fafc}.egp header span{display:block;color:#65758a;font-size:10px;font-weight:800;letter-spacing:.11em;text-transform:uppercase}.egp h2{margin:2px 0 0;font-size:17px;letter-spacing:-.01em}.egp button{border:1px solid #c5cfdb;background:#fff;color:#28465f;border-radius:8px;padding:8px 11px;font-weight:700;cursor:pointer}.egp-metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;background:#e4e9ef;border-bottom:1px solid #e4e9ef}.egp-metrics article{background:#fff;padding:12px 14px;border-top:3px solid transparent}.egp-metrics article.metric-risk{border-top-color:#c2413b;background:#fff8f7}.egp-metrics strong{display:block;font-size:20px;color:#17334d}.egp-metrics span{display:block;margin-top:2px;color:#6a7889;font-size:11px}.egp-finance{display:grid;grid-template-columns:repeat(3,minmax(0,1fr)) 2fr;gap:10px;align-items:center;margin:12px 14px 0;padding:10px 12px;border-radius:9px;border:1px solid #bfe2cf;background:#f5fbf7}.egp-finance.risk{border-color:#f3b8b4;background:#fff6f5}.egp-finance small{display:block;color:#68778a;font-size:9px;font-weight:800;letter-spacing:.07em;text-transform:uppercase}.egp-finance strong{font-size:15px}.egp-finance p{margin:0;color:#526174;font-size:11px;line-height:1.4}.egp-blockers{display:grid;gap:7px;padding:12px 14px}.egp-blockers div,.egp-clear{display:grid;gap:2px;border-left:4px solid #d97706;background:#fffbeb;border-radius:7px;padding:9px 11px}.egp-blockers div.red{border-left-color:#c2413b;background:#fff5f4}.egp-blockers strong{text-transform:capitalize;font-size:12px}.egp-blockers span,.egp-clear span{color:#5f6c7d;font-size:12px}.egp-clear{margin:12px 14px;border-left-color:#27855f;background:#f2fbf6}.egp>footer{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:9px 14px;border-top:1px solid #edf1f5;color:#6a7889;font-size:11px}.egp>footer strong{color:#34485d}.egp-status{padding:14px;color:#65758a}
@media(max-width:900px){.egp-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.egp-finance{grid-template-columns:repeat(3,minmax(0,1fr))}.egp-finance p{grid-column:1/-1}}
@media(max-width:760px){.egp{margin:0 7px 10px}.egp-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.egp-finance{grid-template-columns:1fr 1fr}.egp-finance p{grid-column:1/-1}.egp>footer{align-items:flex-start;flex-direction:column}}
`;
