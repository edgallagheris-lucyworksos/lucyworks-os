# LucyWorks OS — Build Order

## Rule
Do not build isolated dead pages.
Do not build disconnected modules.
Build the platform as usable end-to-end slices.

## Slice 1 — platform spine
Goal:
Unified input -> workflow routing -> owned work item -> role queue -> audit event -> command visibility

Deliver:
- login / role seed
- unified input form
- work item creation from input
- queue by role
- audit trail
- pulse counters from real data

## Slice 2 — communication spine
Goal:
Mail Ops and Messaging attached to operational work.

Deliver:
- thread list
- open thread
- attach thread to work item / episode
- assign owner
- ageing / unresolved indicators
- audit on material decisions

## Slice 3 — timing spine
Goal:
Real time and dependency logic.

Deliver:
- 15-minute scheduling grid
- procedure durations
- turnover windows
- blocker model
- staffing fit check
- delay propagation

## Slice 4 — care continuity
Goal:
Admission to discharge continuity.

Deliver:
- phase tracking
- ward state
- due tasks
- discharge blockers
- owner communication status

## Slice 5 — staffing and safe operations
Goal:
Operational staffing integrity.

Deliver:
- skills matrix
- rota view
- clash detection
- on-call logic
- approval trail
- safe staffing flags

## Slice 6 — ethics and controlled workflows
Goal:
Surface risk, welfare, and compliance.

Deliver:
- ethics flags
- restricted stock workflows
- escalation paths
- compliance audit visibility

## Technical discipline
- one repo
- one architecture
- backend and frontend must both run on first cut
- every button must lead to a usable action or not exist yet
- no placeholder navigation to dead surfaces
