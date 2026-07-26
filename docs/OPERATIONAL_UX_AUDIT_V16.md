# LucyWorks Operational UX Audit v16

## Purpose

LucyWorks must let a verified member of staff understand the current patient situation without hunting through modules or interpreting database output.

Every primary patient view must answer:

1. **Who** is accountable and who is leading the current or next step?
2. **What** is happening and what is the next safe action?
3. **Where** is the patient or work expected to happen?
4. **When** is it happening and what deadline is next?
5. **How** can it proceed, including recorded consent, estimate, medication, handover, result and discharge controls?
6. **Why** is it urgent, blocked or exceptional?

The system presents recorded facts, controls, ownership and evidence gaps. It does not replace professional clinical judgement.

## Blocking defects addressed in v16

### Browser-controlled role scope

The legacy workspace previously accepted a role query from the browser. Scope now comes from verified authentication. A requested compatibility role must match the verified role, and only senior operational roles may inspect another staff member's workspace.

### Unreliable audit attribution

Workspace reads now record the verified actor instead of a synthetic name based on a browser role parameter.

### Page content silently replaced by its title

The shared hospital shell previously substituted a different component when a page title matched a module name. The shell now renders the page's actual content and only supplies predictable navigation and session controls.

### Unauthenticated alert loading

The shared shell now uses the authenticated API client, preserving secure cookies, session expiry handling and consistent request behaviour.

### Excessive module navigation

Daily navigation is reduced to:

- Patient Command
- Hospital Today
- Referrals
- Quick Input
- My Work

Clinical, governance, configuration and deployment tools remain available under **More tools**.

### No single patient situation summary

The new Care Brief combines canonical episode, operational block, conflict, gate and linked-task records into one verified patient summary. It explicitly displays Who, What, Where, When, How and Why.

### Generic Patient Command cards

Patient Command v16 uses the same five-question structure and opens the Care Brief before detailed records or command controls.

## Product rules

### One operational truth

- Canonical episodes describe the patient journey.
- Operational blocks describe time, place, staff and resources.
- Linked work items describe accountable action.
- Conflicts and evidence gates describe why work cannot proceed cleanly.
- Legacy or unlinked data remains visible but cannot be counted as live patient care.

### One next action

Every active episode must have one human-readable next action and one accountable role. Multiple detailed tasks may exist, but the patient summary must not force staff to infer the immediate priority.

### No silent fallback

A live operational page must not silently replace failed API data with a demonstration snapshot. Offline, stale, test and live states must be visibly distinct.

### No autonomous clinical authority

LucyWorks may expose recorded evidence, deadlines, conflicts, options and required approvals. It must not independently diagnose, prescribe, consent, waive a professional duty or make a final clinical decision.

### No role selection as authority

Drop-downs may route work to a role, but they cannot establish the current user's permissions. Authorisation always comes from the verified session and server-side policy.

### No hidden state changes

Every material action must:

- show the expected effect before submission;
- reject stale state;
- identify the verified actor;
- record time, reason and resulting state;
- return a clear success or failure message.

### Mobile first for operational work

Primary controls require:

- minimum 44 px touch targets;
- no browser prompt or alert dialogs;
- no horizontal table dependence;
- keyboard-safe form layouts;
- readable status without colour alone;
- direct recovery after an error;
- no copy-and-paste of an episode reference when it is already known.

## Remaining warnings requiring consolidation

These warnings are deliberately reported by `scripts/audit_operational_ux.py` rather than hidden.

### Episode context in advanced pages

Episode Command, Patient Record and Clinical Execution currently require further consolidation so every `?episode=` deep link automatically loads the selected episode and preserves it across related pages.

### Browser prompts

Some advanced command and clinical pages still use `window.prompt` or `window.alert`. These should become labelled, reviewable forms with reason, evidence and confirmation fields.

### Generic module renderer

Older secondary pages still use generic cards, raw JSON previews or a local snapshot fallback. They must either be retired, converted into a specific operational job, or clearly labelled as technical diagnostics.

### Dense referral intake

Referral intake is functionally governed but still too dense. It should become a staged flow:

1. patient and duplicate check;
2. owner and authority;
3. referral source;
4. clinical need and urgency;
5. documents and review;
6. confirmation and next step.

### Technical field names

Legacy advanced forms still expose identifiers, JSON text and implementation terms. They require domain labels, structured controls, examples and validation.

### Role-specific landing experience

Patient Command filters owned actions, but a later pass should give reception, nursing, clinician, imaging, theatre, pharmacy and operational leadership a tailored default without creating separate sources of truth.

## Release tests

v16 adds automated proof for:

- authenticated Care Brief access;
- Who, What, Where, When and How derived from canonical records;
- recorded consent, blocker, conflict and overdue-task visibility;
- browser role spoofing rejection;
- verified workspace scope;
- verified audit identity;
- primary surface wiring;
- operational-date handling;
- generic core-surface regression;
- title-based shell substitution;
- unauthenticated direct-fetch regression.

Physical Android and hospital workflow acceptance remain separate release gates.
