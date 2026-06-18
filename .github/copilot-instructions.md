# LucyWorksOS coding instructions

Before making changes, read:

1. `AGENTS.md`
2. `docs/LUCYWORKS_SYSTEM_CONTRACT.md`
3. `docs/LUCYWORKS_CONTINUE_HERE.md`
4. `apps/web/lib/day-control-work.ts`
5. `apps/web/lib/day-control-views.ts`

## Non-negotiable rule

LucyWorksOS is one hospital operating system, not a set of disconnected demo pages.

The current source of truth is the generated 15-minute day-control schedule in:

```text
apps/web/lib/day-control-work.ts
```

Use the view adapter:

```text
apps/web/lib/day-control-views.ts
```

Do not create separate standalone sample data for department pages.

## Every feature must answer

```text
who
what
where
when
how
blocker
next action
```

## Must include in full system

```text
arrivals
consults
reception/admin
insurance/admin
client or owner updates
consent and estimates
procedure templates
staff skills
room/resource use
staff welfare
breaks
handover
audit
```

## Correct build sequence

1. Use the generated 15-minute model.
2. Convert views to use the same model.
3. Add state updates.
4. Add backend persistence.
5. Add conflict detection.
6. Add voice-to-work capture.
7. Add patient/subject timeline.

If the change creates another disconnected board, do not build it.
