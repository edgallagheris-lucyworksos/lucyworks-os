# LucyWorks Knowledge and Agent Architecture

LucyWorks needs a controlled knowledge layer, not random prompt text.

## Purpose

This layer separates:

- hospital operating rules
- governance references
- business process notes
- logistics examples
- agent responsibilities
- human approval gates

## Rule

Do not commit private access details, live keys, paid-course dumps, account logins or personal access material.

Store only structure, summaries, tags and permission rules.

## Source classes

| Source | Use | Module |
| --- | --- | --- |
| Hospital operating rules | local workflow and escalation | all |
| Governance guidance | safety and audit checks | LucyGov |
| Business training notes | process, offer, pricing, management cadence | LucyStrategy |
| Logistics examples | stock, task queues, resource movement | LucyOps |

## Agent registry

| Agent | Main job |
| --- | --- |
| LucyOps Agent | resources, theatres, diagnostics, beds, stock |
| LucyFlow Agent | patient movement, blockers, handover |
| LucyHR Agent | rota, cover, fatigue |
| LucyComms Agent | owner updates, estimates, insurance |
| LucyGov Agent | audit, safety, approvals |

## Human approval gates

The system may suggest actions. It must not silently approve high-impact changes.

Approval should be required for:

- clinical priority changes
- safety downgrades
- owner-facing messages
- financial commitments
- HR escalation
- governance closure

## API endpoints

The API registry is exposed at:

- `/api/knowledge/sources`
- `/api/knowledge/agents`
- `/api/knowledge/registry`

## Frontend registry

The frontend source map is stored in:

- `apps/web/lib/knowledge-sources.ts`

## Next implementation step

Add a `LucyKnowledge` admin page that displays sources, agents and approval gates, then connect uploads or summaries into a controlled knowledge store.
