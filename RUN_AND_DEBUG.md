# LucyWorks OS — Run + Debug Guide

This repo is a LucyWorks OS / LucyVet OS working demo spine.

It is not a finished hospital-grade system yet. It is the operational backbone:

- LucyFlow triage
- Lucy Ethics
- Lucy Care
- Decisions
- Blockers
- Escalations
- Owner Comms
- Discharge
- Pharmacy
- Stock
- Pulse
- Episode Command
- Domain automation
- Flow-readiness safety checks
- Smoke tests

## Source of truth

Keep the naming and product language:

- LucyWorks OS = parent operating system
- LucyVet OS = veterinary hospital product
- Lucy Pulse = whole-hospital pressure layer
- Lucy Ethics = welfare / consent / risk layer
- Lucy Care = care continuity layer
- LucyFlow = triage / intake
- LucyRota = staffing / rota / overtime
- Mail Ops = owner comms control
- Episode Command = patient/case spine

Do not rename these into generic SaaS language.

## Install

From repo root:

```bash
npm run backend:install
npm run frontend:install
```

## Run checks

```bash
npm run backend:smoke
npm run backend:safety
npm run frontend:build
```

Or all together:

```bash
npm run check
```

## Run app locally / Codespaces

Terminal 1:

```bash
npm run backend:run
```

Backend runs on:

```text
http://localhost:8000
```

Terminal 2:

```bash
npm run frontend:run
```

Frontend runs on:

```text
http://localhost:3000
```

In Codespaces, open forwarded port 3000 for the frontend and 8000 for the API.

## Main demo pages

```text
/system
/command
/pulse
/episodes/EP-1042
/triage
/ethics
/discharge
/pharmacy
/stock
/schedule
/theatre
/ward
/audit
```

## Backend safety tests

### Main smoke test

```bash
cd backend
python smoke_test.py
```

Checks broad backend routes.

### Domain safety smoke test

```bash
cd backend
python smoke_domain_safety.py
```

Checks:

```text
LucyFlow signal
→ Lucy Ethics signal
→ Discharge blocker
→ Low stock signal
→ Run domain automation
→ Flow readiness check
→ Domain pressure check
```

## Critical endpoints

```text
/api/lucyflow/triage
/api/lucy-ethics
/api/lucy-care/tasks
/api/decisions
/api/blockers
/api/escalations
/api/owner-comms-requirements
/api/discharge-readiness
/api/pharmacy-requests
/api/stock-items
/api/stock-orders
/api/domain-pressure
/api/automation/run-domain-links
/api/flow-readiness/{episode_id}
/api/pulse
/api/episode-command/{episode_ref}
```

## Automation loop

Run:

```text
POST /api/automation/run-domain-links
```

This links:

```text
LucyFlow → Owner Comms
Pain signal → Pharmacy
Lucy Ethics → Work
Blocked Discharge → Pharmacy
Blocked Discharge → Owner Comms
Blocked Discharge → Work
Low Stock → Stock Order
```

## Flow readiness safety check

Run:

```text
GET /api/flow-readiness/{episode_id}
```

Checks:

```text
Discharge readiness
Open pharmacy requests
Open stock orders
Owner comms due
Lucy Ethics flags
Open decisions
Open blockers
Red work items
```

Returns:

```text
ready_for_flow
hard_blocks
warnings
```

## Current honest state

Working demo spine: mostly there.

Still not finished:

- Full auth/security
- Real permissions enforcement
- Robust data validation
- Proper DB migrations
- Real-time websocket updates
- Production deployment
- Clinical governance review
- Full RCVS/VMD compliance review
- Proper test coverage beyond smoke tests
- UX polish for 200-staff live hospital use

## Debug order

If broken, use this order:

1. `npm run backend:install`
2. `npm run backend:smoke`
3. `npm run backend:safety`
4. `npm run frontend:install`
5. `npm run frontend:build`
6. Fix backend model/route errors first
7. Fix frontend TypeScript/build errors second
8. Only then run both servers

## Do not drift

Do not turn LucyWorks into:

- generic checklist app
- generic SaaS dashboard
- generic email inbox
- generic rota board

Every section must connect to:

```text
Patient → Owner → Episode → Location → Specialist/Team → Decision → Next Action → Escalation → Audit
```
