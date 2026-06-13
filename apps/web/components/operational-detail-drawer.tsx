"use client";

import { useState } from "react";
import { recordOperationalAction, type OperationalActionType, type OperationalTarget } from "@/lib/operational-actions";

const actions: Array<[OperationalActionType, string]> = [
  ["assign", "Assign"],
  ["escalate", "Escalate"],
  ["resolve", "Resolve"],
  ["handover", "Handover"],
  ["hold", "Hold"],
  ["request_review", "Request review"],
];

function sourceLabel(value?: string) { return value === "public_verified" ? "public verified" : value === "internal_configurable" ? "configurable" : "mixed"; }

export function OperationalDetailDrawer({ target, onClose }: { target: OperationalTarget | null; onClose: () => void }) {
  const [busy, setBusy] = useState<OperationalActionType | null>(null);
  const [status, setStatus] = useState("ready");
  if (!target) return null;
  async function run(action: OperationalActionType) {
    if (!target) return;
    setBusy(action);
    setStatus("saving");
    try {
      const result = await recordOperationalAction({ action, target, note: `${action} recorded from operational drawer` });
      setStatus(result?.ok ? "saved to audit" : "saved");
    } catch {
      setStatus("not saved - API unavailable");
    } finally {
      setBusy(null);
    }
  }
  return <div className="drawerBackdrop"><style>{css}</style><aside className="drawer"><header><span>{target.type} · {sourceLabel(target.source)}</span><button onClick={onClose}>Close</button></header><h2>{target.label}</h2><dl><dt>Lane</dt><dd>{target.lane || "not set"}</dd><dt>Owner</dt><dd>{target.ownerRole || "unassigned"}</dd><dt>Blocker</dt><dd>{target.blocker || "none recorded"}</dd><dt>Next action</dt><dd>{target.nextAction || "not set"}</dd><dt>Status</dt><dd>{status}</dd></dl><div className="drawerActions">{actions.map(([id, label]) => <button disabled={!!busy} key={id} onClick={() => run(id)}>{busy === id ? "Saving" : label}</button>)}</div><p>All buttons record an operational action through the API and create an audit event when the backend is available.</p></aside></div>;
}

const css = `.drawerBackdrop{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:80;display:flex;justify-content:flex-end}.drawer{width:min(460px,100vw);height:100%;background:#07111f;color:#e6edf7;border-left:1px solid #31557f;padding:20px;box-shadow:-20px 0 60px rgba(0,0,0,.5);overflow:auto}.drawer header{display:flex;justify-content:space-between;gap:12px;align-items:center}.drawer header span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-size:12px;font-weight:900}.drawer h2{font-size:32px;line-height:1;margin:18px 0}.drawer button{border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:999px;padding:10px 12px;font-weight:800}.drawer button:disabled{opacity:.55}.drawer dl{display:grid;grid-template-columns:110px 1fr;gap:10px;background:#0b1728;border:1px solid #243b60;border-radius:16px;padding:14px}.drawer dt{color:#9fb0c6;text-transform:uppercase;font-size:11px}.drawer dd{margin:0}.drawerActions{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:14px 0}.drawer p{color:#a7b5c8}`;
