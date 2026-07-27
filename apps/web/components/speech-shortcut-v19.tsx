"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { SpeechCaptureV19 } from "@/components/speech-capture-v19";

export function SpeechShortcutV19({ mode = "clinical_dictation" }: { mode?: "clinical_dictation" | "consultation_transcription" | "voice_command" | "typed_predictive" }) {
  const params = useSearchParams();
  const episode = params.get("episode") || "";
  const [open, setOpen] = useState(false);

  return <aside style={{ position: "sticky", top: 4, zIndex: 75, padding: "5px 8px", pointerEvents: "none" }}>
    <div style={{ display: "flex", justifyContent: "flex-end" }}>
      <button
        type="button"
        onClick={() => setOpen(value => !value)}
        style={{ pointerEvents: "auto", minHeight: 44, border: 0, borderRadius: 999, padding: "10px 14px", background: open ? "#334155" : "#7c3aed", color: "white", fontWeight: 900, boxShadow: "0 5px 18px rgba(15,23,42,.22)" }}
      >
        {open ? "Close speech review" : "Dictate / transcribe"}
      </button>
    </div>
    {open ? <div style={{ pointerEvents: "auto", marginTop: 7, maxHeight: "calc(100vh - 70px)", overflow: "auto", background: "#e9eef5", border: "1px solid #94a3b8", borderRadius: 16, padding: 6, boxShadow: "0 15px 40px rgba(15,23,42,.28)" }}>
      {episode ? <SpeechCaptureV19 episodeRef={episode} mode={mode} compact /> : <div style={{ background: "#fff7ed", color: "#9a3412", border: "1px solid #fdba74", borderRadius: 10, padding: 12, fontWeight: 800 }}>Open a patient episode first. Speech capture cannot accept patient context supplied separately from the governed episode.</div>}
    </div> : null}
  </aside>;
}
