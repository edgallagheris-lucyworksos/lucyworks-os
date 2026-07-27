"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export function MedicationShortcutV18({ showProtocols = false }: { showProtocols?: boolean }) {
  const [episode, setEpisode] = useState("");
  useEffect(() => {
    setEpisode(new URLSearchParams(window.location.search).get("episode") || "");
  }, []);
  const suffix = episode ? `?episode=${encodeURIComponent(episode)}` : "";
  return <nav aria-label="Medication tools" style={{ position: "sticky", top: 4, zIndex: 80, display: "flex", justifyContent: "flex-end", gap: 7, padding: "5px 8px", pointerEvents: "none" }}>
    <Link href={`/medications${suffix}`} style={{ pointerEvents: "auto", background: "#0f766e", color: "white", borderRadius: 999, padding: "10px 14px", fontWeight: 900, textDecoration: "none", boxShadow: "0 5px 18px rgba(15,23,42,.22)" }}>Medication safety</Link>
    {showProtocols && <Link href={`/medications/protocols${suffix}`} style={{ pointerEvents: "auto", background: "#334155", color: "white", borderRadius: 999, padding: "10px 14px", fontWeight: 900, textDecoration: "none", boxShadow: "0 5px 18px rgba(15,23,42,.22)" }}>Protocol governance</Link>}
  </nav>;
}
