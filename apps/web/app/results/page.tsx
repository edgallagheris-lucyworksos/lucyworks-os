"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type ResultItem = {
  id: number;
  result_type: string;
  review_owner: string;
  status: string;
  required_action?: string;
};

export default function ResultsPage() {
  const [results, setResults] = useState<ResultItem[]>([]);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/results`, { cache: "no-store" });
      setResults(await res.json());
    }
    load();
  }, []);

  async function markReviewed(id: number) {
    await fetch(`${API_BASE}/api/results/${id}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "reviewed" }),
    });
    location.reload();
  }

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician"]}>
      {() => (
        <HospitalShell title="Results" subtitle="Review and action">
          <div style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            {results.map((r) => (
              <div key={r.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <strong>{r.result_type}</strong>
                  <span>{r.status}</span>
                </div>
                <div style={{ color: "#94a3b8" }}>{r.required_action}</div>
                <button onClick={() => markReviewed(r.id)} style={{ marginTop: 8 }}>
                  Mark Reviewed
                </button>
              </div>
            ))}
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
