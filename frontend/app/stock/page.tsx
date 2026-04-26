"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type WorkItem = { id: number; title: string; input_type: string; category: string; urgency: string; owner_role: string; status: string; description: string };

export default function StockPage() {
  const [items, setItems] = useState<WorkItem[]>([]);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/work-items`, { cache: "no-store" });
      const all = await res.json();
      setItems(all.filter((x: WorkItem) => x.category === "stock" || x.input_type === "stock" || x.title.toLowerCase().includes("stock") || x.title.toLowerCase().includes("order")));
    }
    load();
  }, []);

  const open = items.filter((x) => x.status !== "done");
  const urgent = items.filter((x) => x.urgency === "red" || x.urgency === "amber");

  return (
    <AuthGuard allowedRoles={["ops_manager", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Stock" subtitle="Ordering pressure, missing items and operational blockers">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 18 }}>
            <section style={{ border: "1px solid #78350f", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Urgent stock</div><div style={{ fontSize: 34 }}>{urgent.length}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Open stock work</div><div style={{ fontSize: 34 }}>{open.length}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Linked records</div><div style={{ fontSize: 34 }}>{items.length}</div></section>
          </div>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Stock queue</div>
            {items.map((item) => (
              <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><strong>{item.title}</strong><span>{item.urgency.toUpperCase()} • {item.status}</span></div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.description}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>owner {item.owner_role}</div>
              </div>
            ))}
            {!items.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No stock items returned.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
