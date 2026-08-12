# Phone UAT defects — 13 August 2026

Observed on a real Samsung phone against a resumed LucyWorks Codespace.

## Defect 1 — stale resumed build

Observed screen identified itself as Patient-Centred Command v14 while repository `main` had advanced materially beyond that build.

Root cause: Codespace startup reused healthy listeners without proving that they were serving the currently checked-out commit.

Tracked fix: `fix/codespace-stale-resume-v32`.

## Defect 2 — navigation appears non-functional

On the stale mobile build, primary Patient Command actions did not produce usable navigation during physical-device testing.

Retest only after the stale-resume fix is merged and the Codespace is restarted from current `main`; if navigation still fails on the current build, treat it as a separate UI-routing defect.

## Defect 3 — mobile presentation

Observed issues on the stale build included excessive vertical space, oversized header/KPI treatment, horizontal tab clipping and confusing linked/unlinked presentation.

Retest against the current build before deciding which presentation defects remain current.
