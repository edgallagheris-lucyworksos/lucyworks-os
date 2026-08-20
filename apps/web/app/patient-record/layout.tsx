import { Suspense, type ReactNode } from "react";
import { MedicationShortcutV18 } from "@/components/medication-shortcut-v18";
import { SpeechShortcutV19 } from "@/components/speech-shortcut-v19";

export default function PatientRecordLayout({ children }: { children: ReactNode }) {
  return <div className="patient-record-surface">
    <style>{`
      .patient-record-surface{min-height:100vh;background:#f3f6f9}
      .patient-record-surface main{background:#f3f6f9!important;padding:10px!important}
      .patient-record-surface main>header{background:#f8fafc!important;color:#0f172a!important;border:1px solid #cbd5e1!important;border-radius:12px!important;padding:12px 14px!important;box-shadow:0 1px 2px rgba(15,23,42,.04)!important}
      .patient-record-surface main>header h1{font-size:28px!important;line-height:1.08!important;letter-spacing:-.025em!important;margin:2px 0 4px!important}
      .patient-record-surface main>header>div:first-child>div:first-child>div:first-child{color:#64748b!important;letter-spacing:.08em!important}
      .patient-record-surface main>header p{color:#475569!important;margin:7px 0 9px!important;max-width:900px!important}
      .patient-record-surface main>header a{color:#0f172a!important;text-decoration:none!important;font-weight:750!important;padding:7px 9px!important;border:1px solid #cbd5e1!important;border-radius:8px!important;background:white!important}
      .patient-record-surface main>nav{padding:8px 0!important;scrollbar-width:thin}
      .patient-record-surface main>nav button{min-height:40px!important;padding:8px 11px!important;border-radius:8px!important}
      .patient-record-surface main section{box-shadow:none!important}
      @media(max-width:640px){.patient-record-surface main{padding:5px!important}.patient-record-surface main>header{padding:10px!important}.patient-record-surface main>header h1{font-size:24px!important}.patient-record-surface main>header>div:first-child{display:grid!important}.patient-record-surface main>header>div:first-child>div:last-child{gap:6px!important}.patient-record-surface main>header a{flex:1;text-align:center}}
    `}</style>
    <Suspense fallback={null}><MedicationShortcutV18 /><SpeechShortcutV19 mode="clinical_dictation" /></Suspense>
    {children}
  </div>;
}
