import os

from app.main_fixed import app
from app import audit_attribution as _audit_attribution  # noqa: F401
from app.auth import VerifiedIdentityMiddleware
from app.auth_routes import router as auth_router
from app.v3_operational_routes import router as v3_operational_router
from app.ops_engine_routes import router as ops_engine_router
from app.input_routes import router as input_router
from app.department_routes import router as department_router
from app.forecast_routes import router as forecast_router
from app.readiness_routes import router as readiness_router
from app.hr_routes import router as hr_router
from app.catalogue_routes import router as catalogue_router
from app.workspace_routes import router as workspace_router
from app.clinical_director_routes import router as clinical_director_router
from app.dashboard_routes import router as dashboard_router
from app.domain_routes import router as domain_router
from app.episode_state_routes import router as episode_state_router
from app.flow_state_routes import router as flow_state_router
from app.inpatient_routes import router as inpatient_router
from app.live_action_routes import router as live_action_router
from app.mail_ops_routes import router as mail_ops_router
from app.operating_routes import router as operating_router
from app.safety_routes import router as safety_router
from app.startup_routes import router as startup_router
from app.core_machine_routes import router as core_machine_router
from app.workflow_action_routes import router as workflow_action_router
from app.scheduler_routes import router as scheduler_router
from app.conflict_engine_routes import router as conflict_engine_router
from app.role_queue_routes import router as role_queue_router
from app.shadow_mode_routes import router as shadow_mode_router
from app.access_control_routes import router as access_control_router
from app.realtime_routes import router as realtime_router
from app.knowledge_routes import router as knowledge_router
from app.queue_routes import router as queue_router
from app.day_control_routes import router as day_control_router
from app.day_control_conflict_routes import router as day_control_conflict_router
from app.day_control_options_routes import router as day_control_options_router
from app.day_control_assignment_routes import router as day_control_assignment_router
from app.day_control_governance_routes import router as day_control_governance_router
from app.patient_care_routes import router as patient_care_router
from app.evidence_event_routes import router as evidence_event_router
from app.evidence_approval_routes import router as evidence_approval_router
from app.control_plane_routes import router as control_plane_router

# Only the named legacy smoke fixtures may bypass middleware. Production and
# normal development must never set this variable.
if os.getenv("LUCYWORKS_LEGACY_TEST_BYPASS", "false").lower() not in {"1", "true", "yes"}:
    app.add_middleware(VerifiedIdentityMiddleware)

app.include_router(auth_router)
app.include_router(v3_operational_router)
app.include_router(ops_engine_router)
app.include_router(input_router)
app.include_router(department_router)
app.include_router(forecast_router)
app.include_router(readiness_router)
app.include_router(hr_router)
app.include_router(catalogue_router)
app.include_router(workspace_router)
app.include_router(domain_router)
app.include_router(operating_router)
app.include_router(dashboard_router)
app.include_router(clinical_director_router)
app.include_router(episode_state_router)
app.include_router(flow_state_router)
app.include_router(live_action_router)
app.include_router(mail_ops_router)
app.include_router(inpatient_router)
app.include_router(startup_router)
app.include_router(safety_router)
app.include_router(core_machine_router)
app.include_router(workflow_action_router)
app.include_router(scheduler_router)
app.include_router(conflict_engine_router)
app.include_router(role_queue_router)
app.include_router(shadow_mode_router)
app.include_router(access_control_router)
app.include_router(realtime_router)
app.include_router(knowledge_router)
app.include_router(queue_router)
app.include_router(day_control_router)
app.include_router(day_control_conflict_router)
app.include_router(day_control_options_router)
app.include_router(day_control_assignment_router)
app.include_router(day_control_governance_router)
app.include_router(patient_care_router)
app.include_router(evidence_event_router)
app.include_router(evidence_approval_router)
app.include_router(control_plane_router)
