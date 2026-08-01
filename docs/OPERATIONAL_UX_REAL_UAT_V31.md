# Operational UX and Real-UAT Preparation v31

## Objective

Complete Issue #71 without adding a new clinical module. The normal staff workflow remains:

`Patient Command -> Care Brief -> Hospital Today`

Technical administration and legacy compatibility pages are explicitly labelled and linked back to that workflow.

## Implemented controls

1. **Patient context continuity**
   - Episode Command, Patient Record and Clinical Execution read `?episode=` directly.
   - The selected episode is retained in the browser session and appended when staff move between related patient routes.
   - A missing query parameter on a related route is restored from the selected episode; routine copy/paste is not required.

2. **Authenticated operational API access**
   - Operational `fetch(API_BASE...)` calls use the shared authenticated client.
   - Public login and identity-callback endpoints remain the only explicit exception.
   - The shared client retains cookies, CSRF handling and session-expiry behaviour.

3. **Phone-safe evidence capture**
   - Native `prompt()` and `alert()` controls are removed.
   - A labelled modal records evidence, reasons or references with explicit confirmation, keyboard support and 48-pixel touch targets.

4. **Six-stage referral intake**
   1. patient and duplicate check;
   2. owner and authority;
   3. referral source;
   4. clinical need and urgency;
   5. documents and review;
   6. confirmation and next action.

   Duplicate candidates hold patient creation and enter identity review. A successful intake links directly to Care Brief and Episode Command.

5. **Technical and legacy route isolation**
   - Technical administration routes display a blue boundary notice.
   - Legacy compatibility routes display an amber boundary notice.
   - Both provide direct return links to Patient Command, Care Brief and Hospital Today.
   - Raw diagnostic data remains confined to clearly labelled technical surfaces rather than normal patient care.

6. **Operating dates**
   - UTC string truncation is replaced by the browser-local operating-date helper.

## Automated acceptance

The v31 CI gate requires:

- zero errors and zero warnings from `scripts/audit_operational_ux.py`;
- no remaining authenticated `fetch(API_BASE...)` bypass outside public authentication;
- no native browser prompt or alert;
- no UTC-truncated operating date;
- guided-referral, episode-continuity, technical-boundary and evidence-dialog markers;
- the existing connected referral-to-closure proof;
- authority, stale-state and urgent-access proof;
- the complete production web build.

## Real Android acceptance

Run this on the actual Android phone in a fresh supported Codespace:

1. Start the system using the supported Codespace command.
2. Open the forwarded frontend port over HTTPS.
3. Sign in as a development role.
4. Open `/input`.
5. Create patient-linked operational work.
6. Open `/workspace` and find the same work.
7. Open its Care Brief.
8. Move between Care Brief, Patient Record, Clinical Execution and Episode Command without copying the episode reference.
9. Perform an allowed action and record a reason through the labelled evidence dialog.
10. Refresh and confirm the resulting state persists.
11. Confirm the audit record names the verified user rather than browser-supplied identity.
12. Open `/referral-intake` and complete all six stages using touch and the on-screen keyboard.

Record for each step:

- device and browser;
- page and action;
- pass, partial or blocked;
- screenshot or screen recording reference;
- observed result;
- expected result;
- defect/root cause where different;
- whether keyboard, scrolling or touch target obstructed the action.

## Desktop acceptance

Repeat the same patient-context and referral journey on the intended hospital desktop browser. Confirm tab order, focus visibility, error recovery, stale-state handling and no hidden horizontal action area.

## External boundary

Automated checks do not prove physical phone ergonomics, hospital identity integration, real vendor systems, hospital networking, DPIA completion, penetration testing or live patient safety. Those remain governed real-world acceptance controls under Issue #65.
