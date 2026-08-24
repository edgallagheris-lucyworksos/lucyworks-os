# LucyWorks Extension Contract

LucyWorks must remain easy to extend without allowing new departments, workflows, AI tools or integrations to create parallel versions of the hospital.

## Core rule

Every extension consumes the canonical hospital model and contributes through declared commands, events, permissions and views. Extensions must not create shadow copies of patient, episode, staff, room, resource, medication, result, estimate, consent, authority or work state.

## Canonical operating objects

All modules reference the same core identities:

- organisation / site / premises
- patient / episode
- staff / role / capability / authority
- room / area / resource / equipment
- work item / task / procedure
- medication / prescription / administration
- diagnostic order / study / result
- estimate / financial authority / insurance state
- consent / client authority
- communication
- evidence / audit event

## Module contract

Every module must declare:

1. `module_id` and human-readable name.
2. Version and lifecycle state.
3. Canonical objects it reads.
4. Canonical objects it may mutate through commands.
5. Commands it exposes.
6. Events it emits.
7. Events it subscribes to.
8. Required roles/capabilities/authority for consequential actions.
9. UI routes it contributes.
10. External integrations it depends on.
11. Feature flag used to enable/disable it.
12. Acceptance tests proving its real action path.

A module is not complete merely because it renders a page.

## Command rule

State changes happen through explicit commands, not direct ad-hoc writes from UI or AI components.

A consequential command records at minimum:

`command_id -> actor -> authority -> target -> expected state/version -> requested change -> reason -> result -> evidence`

AI may propose commands. AI does not bypass the same authority and validation path used by human users.

## Event rule

Events describe facts that have already happened. They are immutable and named in past tense where possible.

Examples:

- `patient.arrived`
- `referral.accepted`
- `estimate.authorised`
- `insurance.authority_changed`
- `medication.prescribed`
- `medication.administered`
- `diagnostic.resulted`
- `surgery.started`
- `surgery.overran`
- `staff.unavailable`
- `emergency.declared`
- `patient.deteriorated`
- `owner.updated`

Every event carries canonical subject references, premises scope, timestamp, source, actor/provenance, correlation ID and payload version.

## Extension behaviour

Modules react to events and may create proposed work or commands through normal authority gates.

Examples:

- `estimate.changed` -> Insurance creates authority review work.
- `medication.prescribed` -> Pharmacy calculates stock demand.
- `patient.arrived` -> Hospital State recalculates readiness and capacity.
- `surgery.overran` -> Coordination recalculates downstream collisions.
- `emergency.declared` -> Disruption Engine generates ranked replanning options.

## Feature flags

Modules are enabled by stable module IDs, for example:

- `lucy.pharmacy`
- `lucy.insurance`
- `lucy.capture`
- `lucy.disruption`

Disabling a module must not corrupt canonical hospital state or make historical evidence unreadable.

## UI rule

A module may add a specialist workspace, but it must not invent a second patient journey, hospital board, identity model or navigation spine.

Role-specific views are projections of the same hospital state.

## Integration rule

External PMS, PACS, laboratory, pharmacy, insurer and communication systems connect through adapters. Source-system IDs are attached to canonical LucyWorks objects rather than replacing them.

## Acceptance rule

Every serious extension must prove:

1. schema/registry declaration;
2. backend command or query path;
3. event emission/consumption where applicable;
4. authority enforcement;
5. evidence/audit capture for consequential actions;
6. frontend action path when staff interaction exists;
7. automated acceptance test.

## Design test

Before adding a new subsystem ask:

> Can this be expressed as a new consumer/producer of canonical hospital state, commands and events?

If yes, extend the platform. If no, justify changing the core model explicitly in the same pull request.
