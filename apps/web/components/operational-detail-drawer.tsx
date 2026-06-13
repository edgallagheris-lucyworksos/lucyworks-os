"use client";

import { useState } from "react";
import { recordOperationalAction, type OperationalActionType, type OperationalTarget } from "@/lib/operational-actions";
import { destinationFor } from "@/lib/operational-routing";

const actions: Array<[OperationalActionType, string]> = [
  ["assign", "Assign owner"],
  ["escalate", "Escalate"],
  ["resolve", "Resolve"],
  ["handover", "Handover"],
  ["hold", "Hold capacity"],
  ["request_review", "Request review"],
  ["owner_update", "Owner update"],
  ["insurance", "Insurance action"],
  ["pharmacy", "Pharmacy task"],
  ["bed_request", "Bed request"],
  ["imaging_request", "Imaging request"],
  ["theatre_request", "Theatre request"],
];

function sourceLabel(value?: string) { return value === "public_verified" ? "public verified" : value === "internal_configurable" ? "configurable" : "mixed"; }

export function OperationalDetailDrawer({ target, onClose }: { target: OperationalTarget | null; onClose: () => void }) {
  const [busy, setBusy] = useState<OperationalActionType | null>(null);
  const [status, setStatus] = useState("ready");
  const [lastRoute, setLastRoute] = useState("not routed yet");
  if (!target) return null;
  async function run(action: OperationalActionType) {
    if (!target) return;
    const destination = destinationFor(action);
    setBusy(action);
    setStatus("routing");
    setLastRoute(`${destination.destinationRole} · ${destination.destinationQueue} · ${destination.urgency}`);
    try {
      const result = await recordOperationalAction({ action, target, note: `${action} routed to ${destination.destinationRole} via ${destination.destinationQueue}` });
      setStatus(result?.ok ? "routed + saved to audit" : "routed");
    } catch {
      setStatus("not saved - API unavailable");
    } finally {
      setBusy(null);
    }
  }
  return <div className="drawerBackdrop"><style>{css}</style><aside className="drawer"><header><span>{target.type} · {sourceLabel(target.source)}</span><button onClick={onClose}>Close</button></header><h2>{target.label}</h2><dl><dt>Lane</dt><dd>{target.lane || "not set"}</dd><dt>Owner</dt><dd>{target.ownerRole || "unassigned"}</dd><dt>Blocker</dt><dd>{target.blocker || "none recorded"}</dd><dt>Next action</dt><dd>{target.nextAction || "not set"}</dd><dt>Route</dt><dd>{lastRoute}</dd><dt>Status</dt><dd>{status}</dd></dl><div className="drawerActions">{actions.map(([id, label]) => { const destination = destinationFor(id); return <button disabled={!!busy} key={id} onClick={() => run(id)} title={`${destination.destinationRole} · ${destination.destinationQueue}`}><b>{busy === id ? "Saving" : label}</b><small>{destination.destinationRole}<br />{destination.destinationQueue}</small></button>; })}</div><p>Each button routes work to a role queue and records the decision in audit. A later pass should connect queue entries to named staff members on shift.</p></aside></div>;
}

const css = `.drawerBackdrop{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:80;display:flex;justify-content:flex-end}.drawer{width:min(520px,100vw);height:100%;background:#07111f;color:#e6edf7;border-left:1px solid #31557f;padding:20px;box-shadow:-20px 0 60px rgba(0,0,0,.5);overflow:auto}.drawer header{display:flex;justify-content:space-between;gap:12px;align-items:center}.drawer header span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-size:12px;font-weight:900}.drawer h2{font-size:32px;line-height:1;margin:18px 0}.drawer button{border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:16px;padding:10px 12px;font-weight:800;text-align:left}.drawer button:disabled{opacity:.55}.drawer button small{display:block;color:#93a4bb;font-weight:600;margin-top:5px}.drawer dl{display:grid;grid-template-columns:110px 1fr;gap:10px;background:#0b1728;border:1px solid #243b60;border-radius:16px;padding:14px}.drawer dt{color:#9fb0c6;text-transform:uppercase;font-size:11px}.drawer dd{margin:0}.drawerActions{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:14px 0}.drawer p{color:#a7b5c8}`;
