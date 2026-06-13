const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function createQueueWorkItem(payload: { title: string; role: string; queue: string; urgency: string; detail: string; actor?: string }) {
  const res = await fetch(`${API_BASE}/api/queue/work-item`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, actor: payload.actor || "LucyWorks UI" }),
  });
  if (!res.ok) throw new Error(`Queue item failed: ${res.status}`);
  return res.json();
}
