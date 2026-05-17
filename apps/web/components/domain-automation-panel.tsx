"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type AutomationResult = {
  created: {
    owner_comms: number;
    pharmacy_requests: number;
    stock_orders: number;
    work_items: number;
  };
};

export function DomainAutomationPanel() {
  const [status, setStatus] = useState("");
  const [result, setResult] = useState<AutomationResult | null>(null);

  async function runAutomation() {
    setStatus("Running cross-domain links...");
    const res = await fetch(`${API_BASE}/api/automation/run-domain-links`, { method: "POST" });
    const body = await res.json();
    setResult(body);
    setStatus("Domain links updated.");
  }

  return (
    <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div>
          <h3 style={{ margin: 0 }}>Domain automation</h3>
          <div style={{ color: "#94a3b8", marginTop: 6 }}>Runs LucyFlow → Owner Comms, pain → Pharmacy, Discharge → Pharmacy/Owner Comms, Ethics → Work, and low stock → Stock Orders.</div>
        </div>
        <button onClick={runAutomation} style={{ background: "#14b8a6", color: "#020617", border: 0, borderRadius: 12, padding: "10px 14px", fontWeight: 800 }}>Run domain links</button>
      </div>
      {status ? <div style={{ marginTop: 12, color: "#cbd5e1" }}>{status}</div> : null}
      {result ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginTop: 12 }}>
          <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12 }}><div style={{ color: "#94a3b8" }}>Owner Comms</div><strong>{result.created.owner_comms}</strong></div>
          <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12 }}><div style={{ color: "#94a3b8" }}>Pharmacy</div><strong>{result.created.pharmacy_requests}</strong></div>
          <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12 }}><div style={{ color: "#94a3b8" }}>Stock Orders</div><strong>{result.created.stock_orders}</strong></div>
          <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12 }}><div style={{ color: "#94a3b8" }}>Work Items</div><strong>{result.created.work_items}</strong></div>
        </div>
      ) : null}
    </section>
  );
}
