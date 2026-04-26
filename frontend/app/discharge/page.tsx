"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type WorkItem = { id: number; title: string; input_type: string; category: string; urgency: string; owner_role: string; status: string; linked_patient_name?: string | null; linked_episode_ref?: string | null; description: string };

export default function DischargePage() {
  const [items, setItems] = useState<WorkItem[]>([]);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/work-items`, { cache: "no-store" });
      const all = await res.json();
      setItems(all.filter((x: WorkItem) => x.category === "discharge" || x.input_type === "discharge_blocker" || x.title.toLowerCase().includes("discharge")));
    }
    load();
  }, []);

  const blockers = items.filter((x) => x.status !== "done");
  const red = items.filter((x) => x.urgency === "red");

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Discharge" subtitle="Blockers, owner updates, results and handoff readiness">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 18 }}>
            <section style={{ border: "1px solid #7f1d1d", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Red blockers</div><div style={{ fontSize: 34 }}>{red.length}</div></section>
            <section style={{ border: "1px solid #78350f", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Open blockers</div><div style={{ fontSize: 34 }}>{blockers.length}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Total discharge work</div><div style={{ fontSize: 34 }}>{items.length}</div></section>
          </div>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Discharge queue</div>
            {items.map((item) => (
              <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <strong>{item.title}</strong>
                  <span>{item.urgency.toUpperCase()} • {item.status}</span>
                </div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.description}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>owner {item.owner_role} • patient {item.linked_patient_name || "-"}</div>
                {item.linked_episode_ref ? <div style={{ marginTop: 8 }}><Link href={`/episodes/${item.linked_episode_ref}`}>Open episode {item.linked_episode_ref}</Link></div> : null}
              </div>
            ))}
            {!items.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No discharge items returned.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
