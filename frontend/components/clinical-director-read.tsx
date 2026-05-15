"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export function ClinicalDirectorReadPanel() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/director-board`, { cache: "no-store" });
        if (!res.ok) throw new Error("director-board load failed");
        setData(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : "director-board load failed");
      }
    }
    load();
  }, []);

  return (
    <section className="lw-card" style={{ padding: 14 }}>
      <h2 style={{ marginTop: 0 }}>Clinical director read</h2>
      {error ? <p>{error}</p> : null}
      <p style={{ color: "#94a3b8" }}>Cards: {data?.cards?.length ?? 0}</p>
    </section>
  );
}
