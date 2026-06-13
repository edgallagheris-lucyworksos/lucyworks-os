# BVS public site extraction register

Source scope: official Bristol Vet Specialists public website.

## Extracted into LucyWorks

- Public facility profile.
- Public operating theatre count.
- Public interventional suite count.
- Diagnostic imaging equipment profile.
- Public service list.
- Public service workflow map.
- Public workforce groups.
- Public team scale: 100+ professionals.
- Public capacity areas.
- Unknown public capacity markers.
- Referral intake workflow.
- Request-advice workflow.
- Owner consultation journey.
- Insurance and payment workflow.
- Aftercare and discharge workflow.
- TEER / cardiology pathway marker.
- Vet professional / CPD pathway marker.
- Public role and escalation group map.
- Queue destination map.
- Role queue alias expansion.
- Queue work item API.
- Queue-aware drawer on LucyFlow.

## Explicitly not public / must stay configurable

- Total hospital patient capacity.
- Ward bed count.
- ICU bed count.
- Recovery-space count.
- Isolation-space count.
- Dog kennel count.
- Cat kennel count.
- Concurrent day-patient capacity.
- Live rota.
- Named staff on shift.
- Internal escalation rota.
- Actual room-by-room layout.
- Real bed-state board.
- Actual current patient load.

## Required LucyWorks behaviour

- Public facts may seed defaults.
- Public facts must not be treated as live internal state.
- Unknown public capacity must render as configurable capacity.
- Queue actions must route to role queues first.
- Named employee assignment requires active staff/shift data.
- Escalations must go to senior clinical/ops queues unless a live rota selects a named receiver.

## Current build state

- `/bvs-public-map` shows public pathways, role map, workforce groups and capacity areas.
- `/lucy-clinical` shows BVS services, workforce groups and capacity gaps.
- `/flow` has a routed action drawer that sends work to role queues and writes audit.
- `scripts/validate_bvs_public_site_layer.py` checks the BVS public-site model is present.
- `scripts/check-monorepo.sh` runs the BVS public-site validator and queue smoke test.
