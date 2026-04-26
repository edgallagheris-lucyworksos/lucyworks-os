"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type WorkItem = { id: number; title: string; input_type: string; category: string; urgency: string; owner_role: string; status: string; linked_patient_name?: string | null; linked_episode_ref?: string | null; description: string };
type MessageThread = { id: number; episode_id?: number | null; subject: string; source_type: string; owner_role: string; status: string };

function isEthicsItem(item: WorkItem) {
  const text = `${item.title} ${item.description} ${item.category} ${item.input_type}`.toLowerCase();
  return ["ethic", "welfare", "pain", "consent", "financial", "owner refusal", "refuse", "sedation", "neglect", "safeguard"].some((key) => text.includes(key));
}

export default function EthicsPage() {
  const [items, setItems] = useState<WorkItem[]>([]);
  const [threads, setThreads] = useState<MessageThread[]>([]);

  useEffect(() => {
    async function load() {
      const [workRes, threadRes] = await Promise.all([
        fetch(`${API_BASE}/api/work-items`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/message-threads`, { cache: "no-store" }),
      ]);
      const work = await workRes.json();
      setItems(work.filter(isEthicsItem));
      setThreads(await threadRes.json());
    }
    load();
  }, []);

  const red = items.filter((x) => x.urgency === "red");
  const open = items.filter((x) => x.status !== "done");
  const decisionThreads = threads.filter((x) => x.status !== "closed" && (x.subject.toLowerCase().includes("consent") || x.subject.toLowerCase().includes("decision") || x.subject.toLowerCase().includes("owner")));

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Lucy Ethics" subtitle="Welfare, consent, owner communication and escalation risk">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 18 }}>
            <section style={{ border: "1px solid #7f1d1d", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Red ethics flags</div><div style={{ fontSize: 34 }}>{red.length}</div></section>
            <section style={{ border: "1px solid #78350f", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Open ethics work</div><div style={{ fontSize: 34 }}>{open.length}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Decision/comms threads</div><div style={{ fontSize: 34 }}>{decisionThreads.length}</div></section>
          </div>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden", marginBottom: 18 }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Ethics flags</div>
            {items.map((item) => (
              <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><strong>{item.title}</strong><span>{item.urgency.toUpperCase()} • {item.status}</span></div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.description}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>owner {item.owner_role} • patient {item.linked_patient_name || "-"}</div>
                {item.linked_episode_ref ? <div style={{ marginTop: 8 }}><Link href={`/episodes/${item.linked_episode_ref}`}>Open episode {item.linked_episode_ref}</Link></div> : null}
              </div>
            ))}
            {!items.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No explicit ethics flags returned yet.</div> : null}
          </section>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Decision / consent communication threads</div>
            {decisionThreads.map((thread) => (
              <div key={thread.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <strong>{thread.subject}</strong>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{thread.source_type} • {thread.status} • owner {thread.owner_role}</div>
              </div>
            ))}
            {!decisionThreads.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No open decision/consent threads.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
