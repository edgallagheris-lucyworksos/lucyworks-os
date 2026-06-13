# BVS workforce and capacity research

Source date: 2026-06-13.

This file records public operating-scale evidence from the Bristol Vet Specialists website. It is not an internal rota, bed board or ward-capacity disclosure.

## Public workforce scale

The public BVS website states that the team includes over 100 highly skilled professionals.

The public team page includes visible role categories across:

- Consultants and veterinary specialists.
- Residents.
- Interns.
- Registered and specialist nurses.
- ICU nurses.
- Theatre and anaesthesia staff.
- Radiologists and radiographers.
- Therapeutic radiographers.
- Patient care assistants.
- Laboratory support.
- Reception, referral and administration.
- Insurance administration.
- Hospital management.
- Facilities management.

## Public care areas and capacity evidence

Publicly confirmed care/facility areas include:

- Separate dog and cat floors.
- Separate dog and cat waiting areas.
- Separate dog and cat consulting rooms.
- Separate canine and feline kennel areas.
- Dedicated specialist feline wing.
- Isolation units.
- Emergency and critical care service.
- Five operating theatres.
- One interventional suite with fluoroscopy.
- Onsite urgent laboratory testing.
- MRI, CT, ultrasound, digital radiography and fluoroscopy.
- Linear accelerator radiotherapy.

## Capacity status

The public BVS website does not publish total patient capacity, ICU bed count, ward bed count, kennel count, isolation capacity, recovery capacity or concurrent day-patient capacity.

LucyWorks should therefore model capacity as:

- `public_capacity_known` where directly published, e.g. five theatres and one interventional suite.
- `internal_configurable_capacity` for beds, kennels, ICU, recovery, isolation, wards and day-patient throughput.
- `unknown_public_capacity` when public pages confirm the area exists but do not publish a number.

## Modelling consequence

The system must not invent bed or patient-capacity numbers from the public website.

It should instead support configurable capacity for:

- canine wing / dog ward / dog kennels
- feline wing / cat ward / cat kennels
- ICU / critical care
- recovery
- isolation
- day-patient diagnostics and procedures
- owner collection / discharge holding

## LucyWorks routing consequence

Role assignment must support broad professional groups, not only generic nurse/admin/clinician buckets:

- clinical director / hospital manager / ops manager
- head of service / consultant / specialist
- resident / intern
- anaesthesia nurse
- theatre nurse / theatre technician
- ICU nurse
- ward nurse
- feline nurse
- imaging lead / radiographer / radiologist
- oncology / radiotherapy team
- pharmacy or medication owner
- laboratory PCA
- referral coordinator
- insurance administrator
- reception / client care
- facilities manager

## Source URLs

- https://www.bristolvetspecialists.co.uk/about-us/
- https://www.bristolvetspecialists.co.uk/about-us/facilities/
- https://www.bristolvetspecialists.co.uk/about-us/meet-the-team/
- https://www.bristolvetspecialists.co.uk/pet-owners/your-pets-journey/
- https://www.bristolvetspecialists.co.uk/services/emergency-and-critical-care/
- https://www.bristolvetspecialists.co.uk/services/diagnostic-imaging/
