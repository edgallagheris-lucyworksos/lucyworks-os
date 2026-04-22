import Link from "next/link";

export default function HomePage() {
  return (
    <main style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ maxWidth: 900, width: "100%", border: "1px solid #1f2937", borderRadius: 24, padding: 32, background: "#0f172a" }}>
        <h1 style={{ fontSize: 40, margin: 0 }}>LucyWorks OS</h1>
        <p style={{ marginTop: 16, color: "#94a3b8" }}>
          Input-driven hospital command system with routed work, role queues, pulse visibility, audit trail, and role-based access.
        </p>
        <div style={{ marginTop: 24, display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link href="/login" style={{ background: "#14b8a6", color: "#020617", padding: "12px 16px", borderRadius: 12 }}>
            Open access
          </Link>
          <Link href="/workspace" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            Open workspace
          </Link>
          <Link href="/command" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            Clinical Director / Command
          </Link>
          <Link href="/consult" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            Consult Rooms
          </Link>
          <Link href="/ward" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            Ward / ICU
          </Link>
          <Link href="/theatre" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            Theatre / Recovery
          </Link>
          <Link href="/input" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            New input
          </Link>
          <Link href="/queues" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            Queues
          </Link>
          <Link href="/audit" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>
            Audit
          </Link>
        </div>
      </div>
    </main>
  );
}
