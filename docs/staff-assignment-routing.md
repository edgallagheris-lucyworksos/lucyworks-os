# Staff assignment routing

LucyWorks separates four layers:

1. Public BVS role groups.
2. Internal destination roles and queues.
3. Active shift/staff records.
4. Workload-aware named assignment.

## Public BVS layer

The public BVS website can identify role groups such as clinical director, hospital manager, service heads, ICU nurses, imaging team, theatre/anaesthesia staff, referral/admin, insurance and facilities.

Public role groups do not prove who is on shift.

## Queue routing layer

Operational drawer actions route to destination roles and queues first.

Examples:

- `escalate` -> `clinical_director_or_ops_manager` / `escalation_queue`
- `bed_request` -> `ward_or_icu_lead` / `bed_capacity_queue`
- `imaging_request` -> `imaging_lead` / `imaging_queue`
- `theatre_request` -> `theatre_lead` / `theatre_queue`
- `insurance` -> `insurance_admin` / `insurance_queue`
- `pharmacy` -> `pharmacy_owner` / `pharmacy_queue`

## Staff assignment layer

`apps/api/app/staff_assignment.py` maps destination roles and queues to acceptable `StaffMember.role` values.

`/api/queue/work-item` now uses:

1. destination role and queue
2. acceptable staff-role matrix
3. active `StaffMember` records
4. active `Shift` window when available
5. current open workload by `owner_user_id`
6. simple queue/skill text match
7. audit event creation

## Assignment rule

When a queue item is created:

1. Build acceptable staff roles from destination role and queue.
2. Search active staff matching those roles.
3. Prefer staff currently on an active shift.
4. If no active-shift match exists, use active staff in the role pool.
5. Prefer lower open workload.
6. Prefer a staff skills string that matches the queue theme.
7. Assign `owner_user_id` when a match is found.
8. Otherwise leave it in the role queue.

## Still missing

Next improvement should add:

- department/service-specific filtering
- formal skill tags instead of free-text skills
- fatigue / break state
- escalation eligibility
- conflict of responsibility
- named notification delivery
- acceptance / rejection / reassignment loop

Public website data cannot provide that live layer. It must come from rota, shift and internal staffing data.
