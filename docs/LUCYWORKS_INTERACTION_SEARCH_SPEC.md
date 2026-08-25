# LucyWorksOS Interaction, Search and Assisted Entry Specification

## Status

This specification is a required companion to `LUCYWORKS_SPECIFICATION_V1.md` on the architecture branch. It defines how staff should search, select, enter and confirm hospital data.

## Core usability rule

LucyWorksOS should minimise free typing and repeated data entry. Where the system already knows the likely valid choices, staff should normally **search, select, review and confirm** rather than manually retype known facts.

Assistance must remain grounded in canonical hospital data and explicit rules. Suggestions are not an alternative source of truth.

## 1. Context-aware fields

Every structured input must know the entity type it accepts and query the relevant canonical source.

Examples:

- staff field -> StaffMember / Assignment / Shift / Competency / Authority
- medication field -> approved formulary / MedicationProduct / stock / prescribing controls
- patient field -> Patient / Episode / current location / current state
- procedure field -> ProcedureTemplate / service / department context
- room field -> Room / ResourceCapability / availability / turnover state
- estimate field -> CommercialService / PriceVersion / existing EstimateVersion
- complaint field -> Patient / Episode / Estimate / Invoice / Communication / Incident

A structured field must not silently accept arbitrary free text where a canonical entity is required.

## 2. Suggestion ranking

Suggestions should be ranked by a deterministic relevance score using, where applicable:

```text
text match
+ current patient/episode context
+ department/context relevance
+ on-shift / current availability
+ effective professional authority
+ competency
+ resource capability
+ current location
+ recency
+ frequency
+ hospital policy preference
- active conflicts
- expired authority
- unavailable state
```

Ranking may be assisted by AI for fuzzy intent interpretation, but eligibility and safety filtering remain deterministic.

## 3. Staff suggestions

When assigning staff, LucyWorks must show useful operational context with the suggestion rather than only a name.

At minimum, where relevant:

```text
name
role
current department/location
shift status
required competency match
effective authority
availability
current workload/conflict
supervision requirement
```

Unavailable staff may still be searchable when useful, but the reason must be explicit, for example:

```text
Dr Jones — unavailable
Reason: already assigned to Theatre 4, 14:00–15:30
```

or:

```text
Sam Green RVN — not eligible
Reason: MRI competency expired 12 Aug 2026
```

## 4. Medication search and suggestions

Medication entry must search approved canonical medication/formulary records, not generate medication names from an LLM.

Suggestions may display:

```text
generic/product name
form/strength
route
species restrictions
stock/location
controlled-drug status
cold-chain/storage status
relevant active warnings
```

Clinical dose or treatment decisions remain subject to the appropriate professional authority and verification rules. AI may help find or explain a formulary entry but must not invent a medication record.

## 5. Patient and episode search

Patient search must distinguish longitudinal Patient identity from the current Episode.

Results should expose enough context to avoid wrong-patient selection, such as:

```text
patient name
species/breed where recorded
owner/client
patient reference
current episode/status
current location
current responsible service/clinician
```

Duplicate/similar names must be visibly disambiguated.

## 6. Universal hospital search

LucyWorks should provide one global search surface capable of locating, subject to permissions:

```text
patients
episodes
owners/clients
staff
rooms/resources
procedures
medications
results
referrals
work/tasks
estimates
invoices
complaints/incidents
communications
```

Search results should be grouped by entity type and prioritise active/current hospital context.

A result should deep-link to the canonical record or operational view rather than a duplicate search-specific record.

## 7. Command palette

Provide a keyboard-accessible command/search palette, such as `Ctrl+K`, for fast navigation and bounded structured actions.

Examples:

```text
open Milo
find Dr Patel
open MRI 1
create owner update
show blocked imaging work
assign nurse to case
```

Natural-language interpretation may help form a proposed command, but consequential actions must still pass normal identity, authority, validation, conflict and evidence checks.

The system must show a clear confirmation/review step where an interpreted command could materially change hospital state.

## 8. Smart defaults and prefill

Do not ask staff to re-enter canonical facts already known by LucyWorks.

Fields may prefill from current context, for example:

```text
patient
episode
service
current responsible clinician
planned procedure
scheduled room
current estimate
current owner contact
```

Prefilled data must remain visibly reviewable and must not hide uncertainty or stale information.

## 9. Recent and frequent choices

The UI may prioritise recent or frequent valid choices to reduce interaction cost, especially for departmental workflows.

Examples:

```text
recently assigned staff
frequent procedures in department
frequent rooms/resources
frequent communication templates
```

Recency/frequency must never override eligibility, authority, safety or current-state rules.

## 10. Inline validation and explanation

Prefer inline, local explanation over generic modal errors.

Examples:

```text
MRI 1 — unavailable: cleaning until 14:15
Dr Patel — conflict: scheduled in CT 14:00–14:30
Medication — blocked: current patient weight not recorded
Estimate — superseded: newer accepted version exists
```

If an option is disabled, staff should be able to understand **why** and, where LucyWorks can resolve it, what action would remove the blocker.

## 11. Keyboard and touch efficiency

Core search/suggestion controls must support both keyboard and touch workflows.

Recommended keyboard behaviour:

```text
Arrow Up/Down  move through suggestions
Enter          select
Tab            advance
Esc            close/cancel
Ctrl+K         global command/search
```

Touch targets must remain usable on hospital tablets without making desktop operational views excessively large.

## 12. Voice into structured work

Voice capture should feed the same search/entity-resolution/command infrastructure rather than create a separate note silo.

Example:

```text
speech
→ transcript
→ entity resolution
→ proposed structured command/work item
→ staff review
→ normal authority/conflict validation
→ canonical state change
→ EvidenceEvent
```

Ambiguous entity matches must be surfaced for confirmation rather than guessed.

## 13. Search architecture

The search/suggestion layer is a read/service capability over canonical data, not an independent database of hospital truth.

Target flow:

```text
canonical hospital state
        ↓
search/index projection
        ↓
context + permissions + eligibility
        ↓
ranked suggestions
        ↓
UI field / global search / command palette
        ↓
selected canonical entity or proposed command
```

For local/offline development, search must work without a cloud dependency. Start with database-backed indexed search and deterministic ranking. A dedicated search engine may be introduced later only if measured scale/performance justifies it.

## 14. Safety and authority boundaries

Search may reveal only data the current identity is permitted to see.

Suggestion eligibility must be checked server-side for consequential selections.

The frontend may show why an option appears unsuitable, but the backend remains authoritative for:

```text
professional authority
competency
resource conflicts
medication restrictions
consent/estimate requirements
patient identity
state transition validity
```

## 15. Acceptance criteria

A LucyWorks workflow is not considered user-friendly merely because it looks clean. For core operational tasks, acceptance testing should measure whether staff can complete the task with minimal retyping and without needing to remember information already held by the system.

At minimum test:

- staff autocomplete filters/ranks by shift, competency, authority and conflicts;
- medication search uses canonical formulary records;
- patient search safely disambiguates similar names;
- room/resource search explains availability/blockers;
- global search deep-links to canonical records;
- keyboard selection works;
- smart defaults do not create stale or hidden state;
- voice/entity resolution asks for confirmation when ambiguous;
- permissions are enforced server-side;
- suggestions never bypass command validation or EvidenceEvent creation.
