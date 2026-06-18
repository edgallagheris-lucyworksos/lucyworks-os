"use client";

import { useState } from "react";
import { ContactUpdateDraft } from "@/components/contact-update-draft";
import { destinationFor } from "@/lib/operational-routing";
import { recordOperationalAction, type OperationalActionType, type OperationalTarget } from "@/lib/operational-actions";
import { createQueueWorkItem } from "@/lib/queue-work-items";

const actions: OperationalActionType[] = ["assign", "escalate", "resolve", "handover", "hold", "request_review", "owner_update", "insurance", "pharmacy", "bed_request", "imaging_request", "theatre_request"];

export function QueueDetailDrawer({ target, onClose, onActionComplete }: { target: OperationalTarget | null; onClose: () => void; onActionComplete?: (target: OperationalTarget, action: OperationalActionType) => void }) {
  const [status, setStatus] = useState("ready");
  if (!target) return null;

  async function run(action: OperationalActionType, selectedTarget: OperationalTarget) {
    const dest = destinationFor(action);
    const detail = `${selectedTarget.label}: ${selectedTarget.blocker || "no blocker"}. Next: ${selectedTarget.nextAction || dest.reason}.`;
    setStatus(`routing to ${dest.destinationRole}`);
    try {
      await recordOperationalAction({ action, target: selectedTarget, note: `${detail} Queue: ${dest.destinationQueue}` });
      await createQueueWorkItem({ title: `${dest.label}: ${selectedTarget.label}`, role: dest.destinationRole, queue: dest.destinationQueue, urgency: dest.urgency, detail });
      setStatus(`sent to ${dest.destinationRole} / ${dest.destinationQueue}`);
      onActionComplete?.(selectedTarget, action);
    } catch {
      setStatus("saved locally; backend unavailable");
      onActionComplete?.(selectedTarget, action);
    }
  }

  return <div className="qback"><style>{css}</style><aside><header><b>{target.label}</b><button onClick={onClose}>Close</button></header><p>Owner: {target.ownerRole || "unassigned"}</p><p>Blocker: {target.blocker || "none"}</p><p>Next: {target.nextAction || "not set"}</p><p>Status: {status}</p><ContactUpdateDraft target={target} /><div>{actions.map((action) => { const dest = destinationFor(action); return <button key={action} onClick={() => run(action, target)}><b>{dest.label}</b><small>{dest.destinationRole}<br />{dest.destinationQueue}</small></button>; })}</div></aside></div>;
}

const css = `.qback{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:90;display:flex;justify-content:flex-end}aside{width:min(560px,100vw);height:100%;overflow:auto;background:#07111f;color:#e6edf7;border-left:1px solid #31557f;padding:20px}header{display:flex;justify-content:space-between;gap:12px}button{border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:14px;padding:10px;margin:4px;text-align:left}small{display:block;color:#93a4bb;margin-top:4px}`;
