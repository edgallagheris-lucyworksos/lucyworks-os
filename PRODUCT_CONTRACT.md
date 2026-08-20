# LucyWorks product contract

This repository is the product authority. New UI or workflow work must preserve this contract unless the contract is deliberately changed in the same pull request.

## Core operating model

LucyWorks is a referral-hospital operating system, not a collection of demo modules. The staff-facing product resolves hospital work through one consistent chain:

**hospital -> area/room -> patient/episode -> work/procedure -> staff/resource -> state/action -> evidence**

## Hospital command acceptance

The default hospital operating view must remain usable at referral-hospital scale.

- Support at least **40 simultaneous rooms/areas** without creating a thousands-of-pixels-wide room-column board.
- Support at least **100 named staff in the active operational feed** without showing 100 oversized cards.
- Rooms are represented densely; time is the scheduling dimension.
- Staff are summarized by operational load/location and can be searched/drilled into.
- Exceptions, blockers, missing location and missing ownership are visible without opening every patient.
- A user can move from a live case to its care brief, patient record, patient work and episode command.
- Detailed scheduling controls may exist as a secondary view but must not replace the hospital command overview.

## Interaction truthfulness

Every visible interactive control must satisfy one of these conditions:

1. navigate to a valid destination;
2. perform a real state change through the application/backend;
3. open a real detail/control surface; or
4. be disabled with a visible reason and a route to resolve the blocker where one exists.

Decorative buttons, dead links, controls that silently do nothing, and fake success states are prohibited.

## Blocker resolution

A blocker must explain what is missing and, when LucyWorks can resolve it, provide the resolution path. Identity, professional authority, recording/privacy acknowledgement and client consent are separate concepts and must not be collapsed into one checkbox.

## Testing

Rendered screenshots are not sufficient acceptance evidence. Staff-facing changes must include functional browser tests covering navigation or state changes. Hospital-board changes must retain the 40-room / 100-staff scale acceptance test.

## Change discipline

Do not create an alternative master board, navigation model or parallel patient workflow in another feature without reconciling it with this contract. Prefer extending the canonical operating model and shared evidence/authority services over creating another standalone module.
