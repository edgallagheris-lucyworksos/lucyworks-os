import Link from "next/link";

export default function HomePage() {
  return (
    <main style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ maxWidth: 840, width: "100%", border: "1px solid #1f2937", borderRadius: 24, padding: 32, background: "#0f172a" }}>
        <h1 style={{ fontSize: 40, margin: 0 }}>LucyWorks OS</h1>
        <p style={{ marginTop: 16, color: "#94a3b8" }}>
          Input-driven hospital command system with routed work, role queues, pulse visibility, and audit trail.
        </p>
        <div style={{ marginTop: 24, display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link href="/command" style={{ background: "#14b8a6", color: "#020617", padding: "12px 16px", borderRadius: 12 }}>
            Open command view
          </Link>
          <Link href="/input" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            Open input
          </Link>
          <Link href="/queues" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            Open queues
          </Link>
          <Link href="/audit" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            Open audit
          </Link>
        </div>
      </div>
    </main>
  );
}
