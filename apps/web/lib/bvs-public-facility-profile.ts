export type BvsPublicFacilityProfile = {
  sourceDate: string;
  hospitalName: string;
  address: string;
  publicVerifiedOperatingTheatres: number;
  publicVerifiedInterventionalSuites: number;
  theatreLikeSpacesConfigurable: boolean;
  diagnosticUnits: string[];
  treatmentFacilities: string[];
  serviceAreas: string[];
  speciesLayout: string[];
  supportAreas: string[];
};

export const bvsPublicFacilityProfile: BvsPublicFacilityProfile = {
  sourceDate: "2026-06-13",
  hospitalName: "Bristol Vet Specialists",
  address: "Unit 10, More Plus Central Park, Madison Way, Severn Beach, Bristol, BS35 4ER",
  publicVerifiedOperatingTheatres: 5,
  publicVerifiedInterventionalSuites: 1,
  theatreLikeSpacesConfigurable: true,
  diagnosticUnits: [
    "1.5 Tesla Siemens Sempra MRI",
    "64 slice Siemens go.TOP CT scanner",
    "GE LOGIQ E10 ultrasound scanner",
    "digital radiography and fluoroscopy suite",
    "mobile point-of-care ultrasound",
  ],
  treatmentFacilities: [
    "linear accelerator radiotherapy",
    "onsite urgent laboratory testing",
    "operating theatres",
    "interventional suite",
    "isolation units",
  ],
  serviceAreas: [
    "anaesthesia and analgesia",
    "cardiology",
    "dentistry and maxillofacial surgery",
    "dermatology",
    "diagnostic imaging",
    "emergency and critical care",
    "internal medicine",
    "interventional radiology",
    "neurology and neurosurgery",
    "oncology including radiotherapy",
    "ophthalmology",
    "orthopaedics",
    "soft tissue surgery",
  ],
  speciesLayout: [
    "separate dog and cat floors",
    "separate dog and cat waiting areas",
    "separate dog and cat consulting rooms",
    "separate canine and feline kennel areas",
  ],
  supportAreas: [
    "customer experience zone",
    "client and staff car park",
    "outdoor pet exercise space",
    "fully accessible building",
  ],
};
