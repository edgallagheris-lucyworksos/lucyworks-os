import { Suspense, type ReactNode } from "react";
import { SpeechMedicationProposalV19 } from "@/components/speech-medication-proposal-v19";
import { SpeechShortcutV19 } from "@/components/speech-shortcut-v19";

export default function MedicationsLayout({ children }: { children: ReactNode }) {
  return <>
    <Suspense fallback={null}>
      <SpeechShortcutV19 mode="typed_predictive" createClinicalNote={false} />
      <SpeechMedicationProposalV19 />
    </Suspense>
    {children}
  </>;
}
