# LucyWorks OS — Data Model

## Core entities

### Patient
- id
- species
- breed
- name
- owner_id
- flags

### Owner / Client
- id
- name
- contact details
- communication preferences

### Episode
Represents a live visit / admission / treatment pathway.
- id
- patient_id
- status
- service line
- urgency
- owner
- created_at
- current_phase

### Work Item
Generic operational unit created from input.
- id
- input_type
- category
- urgency
- owner_role
- owner_user_id
- status
- due_at
- linked_episode_id
- linked_patient_id
- linked_thread_id

### Task
More granular executable work.
- id
- work_item_id
- task_type
- status
- assigned_to
- due_at
- blocked_by

### Alert
- id
- severity
- reason
- linked_entity_type
- linked_entity_id
- active

### Thread
Used for mail or messaging.
- id
- source_type
- subject
- status
- owner_user_id
- linked_episode_id
- linked_work_item_id

### Message
- id
- thread_id
- sender
- body
- created_at
- material_decision_flag

### Procedure
- id
- episode_id
- type
- planned_duration_mins
- actual_duration_mins
- status
- required_skills

### Theatre Slot
- id
- procedure_id
- theatre_name
- start_at
- end_at
- turnover_mins
- status

### Ward Item
- id
- episode_id
- ward_status
- due_checks
- discharge_blocked

### Shift
- id
- user_id
- role
- start_at
- end_at
- shift_type
- on_call
- approved_overtime

### Staff Member
- id
- name
- role
- skills
- permissions
- current_status

### Stock Item
- id
- sku
- name
- on_hand
- reorder_level
- restricted_flag

### Order
- id
- supplier
- status
- requested_by
- approved_by
- created_at

### Ethics Flag
- id
- episode_id
- type
- severity
- status
- owner

### Audit Event
- id
- actor
- action
- entity_type
- entity_id
- before_state
- after_state
- created_at

## Key principle
The platform should be able to create a work item from any meaningful input, then relate that work item to the correct episode, thread, task, and audit trail.
