import { destinationFor } from "@/lib/operational-routing";

export type OperationalActionType =
  | "assign"
  | "escalate"
  | "resolve"
  | "handover"
  | "hold"
  | "request_review"
  | "owner_update"
  | "insurance"
  | "pharmacy"
  | "bed_request"
  | "imaging_request"
  | "theatre_request";

export type OperationalTarget = {
  id: string;
  label: string;
  type: string;
  lane?: string;
  source?: string;
  ownerRole?: string;
  blocker?: string;
  nextAction?: string;
  route?: string;
};

export type OperationalActionRequest = {
  action: OperationalActionType;
  target: OperationalTarget;
  note?: string;
  actorName?: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function recordOperationalAction(request: OperationalActionRequest) {
  const destination = destinationFor(request.action);
  const res = await fetch(`${API_BASE}/api/actions/operational/record`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: request.action,
      target_id: request.target.id,
      target_label: request.target.label,
      target_type: request.target.type,
      owner_role: destination.destinationRole,
      destination_queue: destination.destinationQueue,
      urgency: destination.urgency,
      blocker: request.target.blocker,
      next_action: request.target.nextAction || destination.reason,
      actor_name: request.actorName || "LucyWorks UI",
      note: request.note || `Route to ${destination.destinationRole} via ${destination.destinationQueue}`,
    }),
  });
  if (!res.ok) throw new Error(`Action failed: ${res.status}`);
  return res.json();
}
