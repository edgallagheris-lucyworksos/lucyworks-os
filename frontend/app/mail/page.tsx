"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function MailPage() {
  const [threads, setThreads] = useState<any[]>([]);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/message-threads`, { cache: "no-store" });
      setThreads(await res.json());
    }
    load();
  }, []);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "admin"]}>
      {() => (
        <HospitalShell title="Mail Ops" subtitle="Threads and communications">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 16 }}>
            <div style={{ border: "1px solid #1f2937", borderRadius: 18 }}>
              {threads.map((t) => (
                <div key={t.id} style={{ padding: 12, borderBottom: "1px solid #1f2937" }}>
                  {t.subject}
                </div>
              ))}
            </div>
            <div style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16 }}>
              Select a thread to view messages.
            </div>
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
