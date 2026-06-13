"use client";

import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { knowledgeSources, lucyAgents } from "@/lib/knowledge-sources";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="lw-card" style={{ padding: 16 }}><h2 style={{ marginTop: 0 }}>{title}</h2>{children}</section>;
}

export default function LucyKnowledgePage() {
  return (
    <AuthGuard allowedRoles={["clinical_director", "ops_manager", "admin"]}>
      {() => (
        <HospitalShell title="LucyKnowledge" subtitle="sources, agents and approval gates">
          <div className="lw-grid" style={{ padding: 20 }}>
            <Card title="Knowledge sources">
              <div style={{ display: "grid", gap: 10 }}>
                {knowledgeSources.map((source) => <article key={source.id} style={{ border: "1px solid #243b60", borderRadius: 14, padding: 12 }}>
                  <strong>{source.label}</strong>
                  <div style={{ color: "#94a3b8" }}>{source.module} · {source.type}</div>
                  <div style={{ marginTop: 6 }}>Human approval: {source.humanApproval ? "required" : "not required for process use"}</div>
                </article>)}
              </div>
            </Card>
            <Card title="Agent registry">
              <div style={{ display: "grid", gap: 10 }}>
                {lucyAgents.map((agent) => <article key={agent.id} style={{ border: "1px solid #243b60", borderRadius: 14, padding: 12 }}>
                  <strong>{agent.label}</strong>
                  <div style={{ color: "#94a3b8" }}>{agent.module}</div>
                  <div style={{ marginTop: 6 }}>{agent.purpose}</div>
                </article>)}
              </div>
            </Card>
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
