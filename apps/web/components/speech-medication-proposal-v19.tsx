"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type MedicationProposal = {
  id: string;
  value: {
    productRef?: string | null;
    productName: string;
    doseExpression?: string | null;
    routeExpression?: string | null;
    frequencyExpression?: string | null;
    calculationPerformed: boolean;
    boundary: string;
  };
  sourceText: string;
  confidence: number;
};

type CaptureView = {
  capture: { capture_ref: string; status: string };
  draft?: { medication_proposals: MedicationProposal[] } | null;
  context: { episodeRef: string; patientRef: string; patientName: string; phase: string };
};

export function SpeechMedicationProposalV19() {
  const params = useSearchParams();
  const speech = params.get("speech") || "";
  const episode = params.get("episode") || "";
  const [data, setData] = useState<CaptureView | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!speech) { setData(null); setError(""); return; }
    let active = true;
    void apiGet<CaptureView>(`/api/v19/speech/captures/${encodeURIComponent(speech)}`)
      .then(result => {
        if (!active) return;
        if (episode && result.context.episodeRef !== episode) {
          setData(null);
          setError("The speech proposal belongs to a different patient episode and has not been loaded.");
          return;
        }
        setData(result); setError("");
      })
      .catch(reason => { if (active) { setData(null); setError(reason instanceof Error ? reason.message : "Speech proposal unavailable"); } });
    return () => { active = false; };
  }, [episode, speech]);

  if (!speech) return null;
  if (error) return <section style={panel("#ef4444", "#fff1f2")}><b>Speech proposal not loaded</b><p style={{ margin: 0 }}>{error}</p></section>;
  if (!data) return <section style={panel("#94a3b8", "#f8fafc")}><b>Loading speech proposal…</b></section>;

  const proposals = data.draft?.medication_proposals || [];
  return <section style={panel("#f59e0b", "#fffbeb")}>
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
      <div><small style={{ fontWeight: 950, letterSpacing: ".1em", color: "#92400e" }}>SPEECH PROPOSAL · NOT A CALCULATION OR PRESCRIPTION</small><h2 style={{ margin: "4px 0" }}>{data.context.patientName}</h2><p style={{ margin: 0 }}>{data.context.episodeRef} · {data.capture.status}</p></div>
      <b style={{ color: "#92400e" }}>{proposals.length} medicine expression{proposals.length === 1 ? "" : "s"}</b>
    </div>
    {proposals.length ? <div style={{ display: "grid", gap: 7, marginTop: 10 }}>{proposals.map(item => <article key={item.id} style={{ display: "grid", gap: 4, background: "white", border: "1px solid #fcd34d", borderRadius: 9, padding: 9 }}><b>{item.value.productName}</b><span>{item.value.doseExpression || "Dose not heard"} · {item.value.routeExpression || "Route not heard"} · {item.value.frequencyExpression || "Frequency not heard"}</span><small style={{ color: "#64748b" }}>{item.value.boundary}</small><small style={{ color: "#64748b" }}>Source: {item.sourceText} · confidence {Math.round(item.confidence * 100)}%</small></article>)}</div> : <p>No medication expression was extracted from this capture.</p>}
    <p style={{ marginBottom: 0, fontWeight: 800 }}>Select the exact product and an approved protocol below. Medication Foundation v18 performs all arithmetic, patient checks, professional review and prescribing controls.</p>
  </section>;
}

function panel(border: string, background: string): React.CSSProperties {
  return { margin: "7px 8px", border: `1px solid ${border}`, borderLeft: `7px solid ${border}`, borderRadius: 12, background, color: "#0f172a", padding: 12, fontFamily: "Inter,system-ui,sans-serif" };
}
