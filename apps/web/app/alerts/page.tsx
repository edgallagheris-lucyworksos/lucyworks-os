"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type AlertItem = {
  alert_type: string;
  severity: string;
  detail: string;
};

type AlertsResponse = {
  total_alerts: number;
  high_alerts: number;
  alerts: AlertItem[];
};

export default function AlertsPage() {
  const [data, setData] = useState<AlertsResponse | null>(null);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/alerts`, { cache: "no-store" });
      setData(await res.json());
    }
    load();
  }, []);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Alerts" subtitle="Derived operational alert stream">
          {!data ? <p>Loading alerts...</p> : null}
          {data ? (
            <div style={{ display: "grid", gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                <div style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}>
                  <div style={{ color: "#94a3b8" }}>Total alerts</div>
                  <div style={{ fontSize: 34, marginTop: 8 }}>{data.total_alerts}</div>
                </div>
                <div style={{ border: "1px solid #7f1d1d", borderRadius: 18, padding: 16, background: "#0f172a" }}>
                  <div style={{ color: "#94a3b8" }}>High alerts</div>
                  <div style={{ fontSize: 34, marginTop: 8 }}>{data.high_alerts}</div>
                </div>
              </div>
              <div style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                {data.alerts.map((alert, index) => (
                  <div key={`${alert.alert_type}-${index}`} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                      <strong>{alert.alert_type}</strong>
                      <span>{alert.severity}</span>
                    </div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>{alert.detail}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
