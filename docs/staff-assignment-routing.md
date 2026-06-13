# Staff assignment routing

LucyWorks now separates three different layers:

1. Public BVS role groups.
2. Internal destination roles and queues.
3. Active staff records used for named assignment.

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

`apps/api/app/staff_assignment.py` maps destination roles and queues to acceptable active `StaffMember.role` values.

`/api/queue/work-item` uses that matrix:

1. build acceptable staff roles from destination role and queue
2. search active staff
3. assign `owner_user_id` if a matching active staff member exists
4. otherwise leave the item in the role queue
5. create an audit event either way

## Required future layer

Current assignment selects the first matching active staff member by role/name order.

Next improvement should select by:

- active shift window
- department/service
- skill tag
- workload count
- fatigue / break state
- escalation eligibility
- conflict of responsibility

Public website data cannot provide that live layer. It must come from rota/shift/internal staffing data.
