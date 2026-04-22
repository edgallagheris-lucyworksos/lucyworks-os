# LucyWorks OS — Hospital Topology Model

## Why this matters

LucyWorks OS is not just a list of work items.
It has to understand where work is happening in the hospital, what area it belongs to, what rooms and resources are affected, and what nearby operational dependencies exist.

A work item should be locatable in the physical hospital.

## Topology layers

### 1. Site
The overall hospital site.

### 2. Section / Department
High-level operational sections such as:
- reception / meet and greet
- waiting area
- emergency / triage
- wards
- ICU / HDU
- theatres
- prep / anaesthesia
- imaging
- labs
- consult rooms
- discharge area
- pharmacy / stores
- staff base / admin
- isolation

### 3. Room / Space
Concrete operational locations such as:
- consult room 1
- consult room 2
- theatre 1
- theatre 2
- ICU bay A
- ward kennel row B
- imaging room
- CT room
- pharmacy store room
- front desk

### 4. Bed / Bay / Slot / Resource position
Where needed, the system should track finer-grain locations such as:
- kennel / cage
- bay
- treatment table
- theatre slot
- imaging slot
- bed space

## Why location matters operationally

Location changes:
- who should see the work
- what dependencies it has
- what staffing model applies
- what prep rules apply
- what handoff path applies
- what timing assumptions apply
- what nearby pressure signals matter

## Examples

### Example 1
An inpatient update in ICU is not just a generic task.
It belongs to:
- section: ICU
- room: ICU bay area
- patient location: bay A
- owner roles: nurse + clinician
- dependencies: monitoring / meds / owner comms / discharge planning

### Example 2
A procedure overrun belongs to:
- section: theatres
- room: theatre 2
- linked prep room
- linked recovery area
- downstream turnover impact
- staffing impact

### Example 3
A communication issue at front desk belongs to:
- section: reception
- room: front desk
- owner role: admin / reception
- dependency: intake completeness / owner contact / admission flow

## Topology-aware views

The system should support filtering and grouping by:
- section
- room
- resource
- patient location
- operational zone

## Command implications

Lucy Pulse should be able to show pressure by location, for example:
- theatres overloaded
- ICU running hot
- ward discharge backlog
- imaging delayed
- front desk intake queue building

## Minimum topology needed in first real build

At minimum, each work item should be able to store:
- section
- room
- optional patient location
- optional resource name

Without this, LucyWorks OS cannot behave like a real hospital operations system.
