# LucyWorksOS canonical consolidation audit

Status: canonicalisation decision complete. This document controls removal of the duplicate top-level implementations.

## Decision

The only active LucyWorksOS implementation is:

```text
apps/web   # staff-facing Next.js product
apps/api   # backend/API, persistence, auth, governance and operational services
```

The top-level `frontend/` and `backend/` directories are legacy snapshots. They are not separate products and must not receive new development.

## Evidence

### Root execution points at `apps/*`

The root `package.json` identifies the product as `0.10.0-one-system` and every active install/run/build command targets `apps/api` or `apps/web`.

### Current contracts point at `apps/*`

`PRODUCT_CONTRACT.md`, `AGENTS.md`, the current system contract and architecture validators define one hospital operating model and current canonical files under `apps/*`.

### Frontend parity / supersession

The legacy `frontend/app` contains routes such as:

```text
actions
admissions
alerts
audit
catalogues
clinical-director
command
conflicts
consult
dashboard
departments
discharge
episodes
ethics
flow-state
hospital-board
hr
input
login
mail
pharmacy
pulse
results
rooms
rota
schedule
staff
stock
system
theatre
triage
ward
workspace
```

The canonical `apps/web/app` contains the corresponding operating surfaces and has expanded beyond them with current system-control, auth, automation, clinical-execution, care, compliance, episode-command, hospital-ops, hospital-configuration, hospital-intelligence and other connected surfaces.

Several matching legacy and canonical routes have different tree SHAs because canonical routes continued to evolve after the legacy copy was made. The legacy tree is therefore not an authoritative implementation.

### Backend parity / supersession

A representative comparison shows legacy backend modules carried forward into `apps/api/app` with identical Git blob SHAs, including:

```text
assignment_directory_models.py
canonical_modules.py
canonical_roles.py
canonical_triage.py
capability_engine.py
catalogue_models.py
catalogue_routes.py
clinical_director_routes.py
```

The canonical API has then moved substantially beyond the legacy snapshot with current authentication/session/access-control, audit attribution, Alembic migrations, operator control, BVS operational services, clinical execution, compliance/safety, conflict engine, connected-surface services and their smoke/acceptance tests.

### Current delivery work is canonical

Recent consolidation, hospital-scale and professional UI work targets `apps/web`, `apps/api`, canonical scripts and canonical browser/acceptance tests. The root check pipeline also runs the canonical monorepo.

## Migration conclusion

No active runtime reason was found to preserve `frontend/` or `backend/` as a second implementation. Their useful concepts are already represented in the canonical product or have been superseded by newer canonical services and surfaces.

Git history preserves the old implementation, so deleting the duplicate working-tree directories does not destroy provenance or make old code unrecoverable.

## Deletion gate

The duplicate directories may be removed when the consolidation branch satisfies all of the following:

1. `AGENTS.md` explicitly locks new development to `apps/web` + `apps/api`.
2. Root scripts continue to target canonical paths only.
3. The canonical architecture validator passes.
4. The full root `npm run check` pipeline passes in CI or on a clean local checkout.
5. No canonical import, runtime script or deployment configuration depends on `frontend/` or `backend/`.

## Post-deletion rules

After removal:

- Never recreate top-level `frontend/` or `backend/`.
- New UI belongs under `apps/web`.
- New backend/domain work belongs under `apps/api`.
- Shared operating concepts must remain connected through the canonical backend state, audit/evidence layer and hospital operating model.
- If historical behaviour is needed, recover it from Git history and migrate the behaviour into the canonical implementation rather than restoring the legacy tree.

## Local/offline coding-agent rule

A local coding agent must open the repository root, read `AGENTS.md`, and treat only `apps/web` and `apps/api` as writable product code unless a task explicitly names another current support directory such as `scripts/`, `docs/`, `.github/`, or infrastructure configuration.
