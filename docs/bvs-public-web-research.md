# BVS public web research notes

Source date: 2026-06-13.

This file records public facts from the official Bristol Vet Specialists website. It is a public-facing facility profile, not a complete internal operating map.

## Identity and location

- Name: Bristol Vet Specialists.
- Description: state-of-the-art small animal veterinary referral hospital for the South West, Wales and beyond.
- Address: Unit 10, More Plus Central Park, Madison Way, Severn Beach, Bristol, BS35 4ER.
- Company: trading name of CVS (UK) Limited.

## Public facility facts

- Separate floors for cats and dogs.
- Customer experience zone.
- Separate dog and cat waiting areas.
- Separate dog and cat consulting rooms.
- Dedicated client and staff car park.
- Fully accessible building.
- Outdoor space and grassland for pets.

## Public clinical service areas

- Anaesthesia and analgesia.
- Cardiology.
- Dentistry and maxillofacial surgery.
- Dermatology.
- Diagnostic imaging.
- Emergency and critical care.
- Internal medicine.
- Interventional radiology.
- Neurology and neurosurgery.
- Oncology, including radiotherapy.
- Ophthalmology.
- Orthopaedics.
- Soft tissue surgery.

## Public equipment and facilities

- Five new spacious operating theatres.
- Dedicated interventional suite with fluoroscopy.
- Linear accelerator for radiotherapy.
- 1.5 Tesla Siemens Sempra MRI.
- 64 slice Siemens go.TOP CT scanner.
- GE LOGIQ E10 ultrasound scanner.
- Digital radiography and fluoroscopy suite.
- Mobile point-of-care ultrasound.
- Onsite urgent laboratory testing.
- Separate canine and feline kennel areas.
- Isolation units.

## Operational modelling consequence

The public page says five operating theatres plus an interventional suite. LucyWorks should not hard-code eleven public theatres unless internal evidence confirms that number.

Recommended model:

- public_verified_operating_theatres: 5
- public_verified_interventional_suites: 1
- theatre_like_spaces: configurable
- diagnostic_units: MRI, CT, ultrasound, radiography, fluoroscopy, mobile ultrasound
- radiotherapy: linear accelerator
- species_layout: separate dog and cat floors, waiting areas and consulting rooms

## Source URLs

- https://www.bristolvetspecialists.co.uk/
- https://www.bristolvetspecialists.co.uk/about-us/
- https://www.bristolvetspecialists.co.uk/about-us/facilities/
- https://www.bristolvetspecialists.co.uk/about-us/how-to-find-us/
- https://www.bristolvetspecialists.co.uk/services/diagnostic-imaging/
- https://www.bristolvetspecialists.co.uk/services/emergency-and-critical-care/
