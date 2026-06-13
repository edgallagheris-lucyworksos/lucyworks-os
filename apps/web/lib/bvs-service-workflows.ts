export type BvsWorkflow = {
  id: string;
  label: string;
  lane: string;
  publicBasis: string;
  lucyModule: string;
  commonBlockers: string[];
  nextActions: string[];
};

export const bvsServiceWorkflows: BvsWorkflow[] = [
  { id: "diagnostic-imaging", label: "Diagnostic imaging", lane: "imaging", publicBasis: "MRI, CT, ultrasound, radiography and fluoroscopy", lucyModule: "LucyOps", commonBlockers: ["slot", "sedation", "report owner", "handover"], nextActions: ["assign imaging owner", "confirm anaesthesia cover", "book result review"] },
  { id: "emergency-critical-care", label: "Emergency and critical care", lane: "ecc", publicBasis: "assessment, stabilisation, investigation and intensive care", lucyModule: "LucyFlow", commonBlockers: ["triage owner", "ICU space", "senior review", "handover"], nextActions: ["assign ECC owner", "confirm ICU capacity", "escalate unstable case"] },
  { id: "oncology-radiotherapy", label: "Oncology and radiotherapy", lane: "oncology", publicBasis: "oncology service and linear accelerator radiotherapy", lucyModule: "LucyClinical", commonBlockers: ["treatment plan", "machine slot", "anaesthesia", "owner consent"], nextActions: ["confirm treatment plan", "hold machine slot", "prepare owner update"] },
  { id: "interventional-radiology", label: "Interventional radiology", lane: "interventional", publicBasis: "dedicated interventional suite with fluoroscopy", lucyModule: "LucyOps", commonBlockers: ["fluoroscopy", "kit", "anaesthesia", "recovery"], nextActions: ["confirm IR kit", "assign suite owner", "confirm recovery route"] },
  { id: "soft-tissue-surgery", label: "Soft tissue surgery", lane: "surgery", publicBasis: "soft tissue surgery service", lucyModule: "LucyOps", commonBlockers: ["theatre", "kit", "anaesthesia", "recovery"], nextActions: ["sequence theatre", "confirm sterile kit", "confirm recovery space"] },
  { id: "orthopaedics", label: "Orthopaedics", lane: "surgery", publicBasis: "orthopaedics service", lucyModule: "LucyOps", commonBlockers: ["theatre", "implants", "imaging", "recovery"], nextActions: ["check implants", "confirm theatre slot", "link imaging"] },
  { id: "neurology-neurosurgery", label: "Neurology and neurosurgery", lane: "neuro", publicBasis: "neurology and neurosurgery service", lucyModule: "LucyClinical", commonBlockers: ["MRI", "CT", "senior decision", "theatre"], nextActions: ["prioritise imaging", "assign neuro owner", "prepare theatre hold"] },
  { id: "internal-medicine", label: "Internal medicine", lane: "medicine", publicBasis: "internal medicine service", lucyModule: "LucyClinical", commonBlockers: ["results", "sample", "owner update", "ward bed"], nextActions: ["assign result owner", "release lab blocker", "prepare discharge plan"] },
  { id: "cardiology", label: "Cardiology", lane: "cardiology", publicBasis: "cardiology service", lucyModule: "LucyClinical", commonBlockers: ["scan slot", "clinician review", "owner update"], nextActions: ["book review", "assign clinical owner", "update owner"] },
  { id: "ophthalmology", label: "Ophthalmology", lane: "ophthalmology", publicBasis: "ophthalmology service", lucyModule: "LucyClinical", commonBlockers: ["consult room", "procedure slot", "owner consent"], nextActions: ["assign service owner", "confirm procedure readiness", "prepare consent"] },
  { id: "dermatology", label: "Dermatology", lane: "dermatology", publicBasis: "dermatology service", lucyModule: "LucyClinical", commonBlockers: ["consult room", "sample", "lab review"], nextActions: ["assign review owner", "track sample", "set callback"] },
  { id: "dentistry-maxillofacial", label: "Dentistry and maxillofacial surgery", lane: "dentistry", publicBasis: "dentistry and maxillofacial surgery service", lucyModule: "LucyOps", commonBlockers: ["theatre", "imaging", "kit", "recovery"], nextActions: ["confirm kit", "link imaging", "confirm recovery"] },
  { id: "anaesthesia-analgesia", label: "Anaesthesia and analgesia", lane: "anaesthesia", publicBasis: "anaesthesia and analgesia service", lucyModule: "LucyOps", commonBlockers: ["anaesthetist", "pain plan", "procedure cover"], nextActions: ["assign anaesthesia cover", "confirm pain plan", "clear procedure gate"] },
];

export const bvsSpeciesSeparation = [
  "separate dog and cat floors",
  "separate dog and cat waiting areas",
  "separate dog and cat consulting rooms",
  "separate canine and feline kennel areas",
];
