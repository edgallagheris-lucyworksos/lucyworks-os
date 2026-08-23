# LucyWorks OS — Current Build + Debug Handover

## Current architecture

LucyWorksOS is one connected referral-hospital operating system.

The canonical implementation is:

```text
apps/web   # Next.js staff-facing product
apps/api   # FastAPI backend, domain services, persistence, auth and governance
```

Top-level `frontend/` and `backend/` were earlier implementation snapshots. They are not current run targets and must not receive new product work. See `docs/CANONICAL_CONSOLIDATION_AUDIT.md`.

## Product authority

Read these before changing product behaviour:

1. `PRODUCT_CONTRACT.md`
2. `AGENTS.md`
3. `docs/LUCYWORKS_SYSTEM_CONTRACT.md`
4. `docs/LUCYWORKS_CONTINUE_HERE.md`

The operating principle is one hospital model with connected views, not independent departmental apps.

## Canonical frontend

```text
apps/web
```

Important operating-model files include:

```text
apps/web/lib/day-control-work.ts
apps/web/lib/day-control-views.ts
apps/web/components/day-control-grid.tsx
```

The current product also contains the newer hospital command, episode, care, clinical execution, governance, access, automation and system-control surfaces under `apps/web/app`.

## Canonical backend

```text
apps/api
```

Run entrypoint:

```text
apps/api/app/main.py
```

The canonical backend contains authentication and access control, audit attribution, migrations, hospital operations, scheduling/day control, conflict handling, care, evidence/governance and newer operational services. Do not route new functionality back through the deleted/legacy top-level backend.

## Install

From the repository root:

```bash
npm run backend:install
npm run frontend:install
```

## Full validation

From the repository root:

```bash
npm run check
```

This uses the canonical root validation pipeline in `scripts/check-all.sh`, including architecture/system checks, backend smoke/safety validation and the frontend build.

Do not treat a visual screenshot as sufficient acceptance for staff-facing behaviour. Preserve functional browser and hospital-scale acceptance tests required by `PRODUCT_CONTRACT.md`.

## Run locally

Use two terminals from the repository root.

### Terminal 1 — API

```bash
npm run backend:run
```

Default API port:

```text
8000
```

### Terminal 2 — web

```bash
npm run frontend:run
```

Default web port:

```text
3000
```

Or use the repository's canonical combined development scripts where appropriate:

```bash
npm run dev
```

## Debug order

When something fails:

1. Confirm you are working in `apps/web` / `apps/api`, not a historical directory.
2. Run `npm run check` and capture the first real failure.
3. Fix the smallest root cause; do not redesign adjacent modules.
4. Run the relevant focused test.
5. Run the full check again.
6. Review `git diff` before accepting the change.

## Connected-system rule

A feature is not complete merely because a page renders.

Changes must preserve the chain:

```text
hospital
→ area / room
→ patient / episode
→ work / procedure
→ staff / resource
→ state / action
→ evidence / audit
```

A change in one operational surface must update shared canonical state so the rest of LucyWorks can reflect it. Do not create a private page-level database, alternate master schedule, duplicate patient workflow or disconnected board.

## AI / coding-agent rule

AI may assist development and operational text handling, but it is not system authority.

For coding agents:

- read `AGENTS.md` first;
- work in a feature branch;
- analyse before editing when scope is uncertain;
- do not write new product code into legacy paths;
- do not change architecture, auth, safety/governance, schema or deployment boundaries without explicit scope;
- run tests and show the diff after edits.

For LucyWorks runtime AI:

- use structured inputs/outputs;
- validate model output before persistence;
- hard rules, permissions, audit and human authority remain authoritative;
- local Ollama models may be used as an implementation detail, not as the source of hospital truth.

## Current consolidation task

The repository is being reduced to one obvious active implementation. The canonical branch work should:

1. lock `apps/web` + `apps/api` as the only product implementation;
2. preserve any verified useful legacy behaviour through Git history/migration;
3. remove duplicate top-level `frontend/` and `backend/` once the canonical checks are green;
4. continue all subsequent LucyWorks work only in the canonical monorepo.
