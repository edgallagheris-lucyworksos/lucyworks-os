"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Thread = {
  id: number;
  subject: string;
  source_type: string;
  owner_role: string;
  status: string;
  episode_id?: number | null;
};

type Entry = {
  id: number;
  thread_id: number;
  sender_name: string;
  direction: string;
  body: string;
  material_decision_flag: boolean;
  created_at: string;
};

export default function MailPage() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [selected, setSelected] = useState<Thread | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [reply, setReply] = useState("");

  async function loadThreads() {
    const res = await fetch(`${API_BASE}/api/message-threads`, { cache: "no-store" });
    const data = await res.json();
    setThreads(data);
    if (!selected && data.length) setSelected(data[0]);
  }

  async function loadEntries(threadId: number) {
    const res = await fetch(`${API_BASE}/api/message-threads/${threadId}/entries`, { cache: "no-store" });
    setEntries(await res.json());
  }

  useEffect(() => {
    loadThreads();
  }, []);

  useEffect(() => {
    if (selected) loadEntries(selected.id);
  }, [selected?.id]);

  async function sendReply() {
    if (!selected || !reply.trim()) return;
    await fetch(`${API_BASE}/api/messages/${selected.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sender_name: "LucyWorks User", direction: "outbound", body: reply, material_decision_flag: true, actor_name: "Mail Ops" }),
    });
    setReply("");
    await loadEntries(selected.id);
  }

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "admin"]}>
      {() => (
        <HospitalShell title="Mail Ops" subtitle="Owner updates, clinical threads, and material decisions">
          <div style={{ display: "grid", gridTemplateColumns: "minmax(260px, 1fr) minmax(360px, 2fr)", gap: 16 }}>
            <div style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
              <div style={{ padding: 14, background: "#0f172a", fontWeight: 700 }}>Threads</div>
              {threads.map((thread) => (
                <button
                  key={thread.id}
                  onClick={() => setSelected(thread)}
                  style={{ width: "100%", textAlign: "left", padding: 14, border: 0, borderTop: "1px solid #1f2937", background: selected?.id === thread.id ? "#111827" : "transparent", color: "#f8fafc" }}
                >
                  <strong>{thread.subject}</strong>
                  <div style={{ color: "#94a3b8", marginTop: 4 }}>{thread.source_type} • {thread.status} • {thread.owner_role}</div>
                </button>
              ))}
            </div>

            <div style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
              <div style={{ padding: 14, background: "#0f172a", fontWeight: 700 }}>
                {selected ? selected.subject : "Select a thread"}
              </div>
              <div style={{ padding: 14, display: "grid", gap: 12 }}>
                {entries.map((entry) => (
                  <div key={entry.id} style={{ border: "1px solid #1f2937", borderRadius: 14, padding: 12, background: entry.direction === "outbound" ? "#111827" : "#020617" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                      <strong>{entry.sender_name}</strong>
                      <span>{entry.direction}{entry.material_decision_flag ? " • decision" : ""}</span>
                    </div>
                    <div style={{ color: "#cbd5e1", marginTop: 8 }}>{entry.body}</div>
                  </div>
                ))}
                {selected ? (
                  <div style={{ display: "grid", gap: 8 }}>
                    <textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Write reply / owner update / clinical note" style={{ minHeight: 90, borderRadius: 12, padding: 12 }} />
                    <button onClick={sendReply} style={{ padding: 12, borderRadius: 12, background: "#14b8a6", color: "#020617", border: 0 }}>Send reply</button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
