import os

from app.main_fixed import app
from app import audit_attribution as _audit_attribution  # noqa: F401
from app import database_exception_handlers as _database_exception_handlers  # noqa: F401
from app import hospital_ops_runtime_patch as _hospital_ops_runtime_patch  # noqa: F401
from app import production_readiness_runtime_patch as _production_readiness_runtime_patch  # noqa: F401
from app import compliance_safety_readiness_patch as _compliance_safety_readiness_patch  # noqa: F401
from app import bvs_v6_runtime_patch as _bvs_v6_runtime_patch  # noqa: F401
from app import integration_retry_runtime as _integration_retry_runtime  # noqa: F401
from app import auth_scope_v25_patch as _auth_scope_v25_patch  # noqa: F401
from app.auth import VerifiedIdentityMiddleware
from app.verified_actor_attribution_v25 import VerifiedActorAttributionMiddlewareV25
from app.production_middleware import ProductionProtectionMiddleware
from app.legacy_write_retirement import LegacyWriteRetirementMiddleware
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
from app.integration_routes import router as integration_router
from app.hospital_ops_routes import router as hospital_ops_router
from app.hospital_ops_extension_routes import router as hospital_ops_extension_router
from app.production_readiness_routes import router as production_readiness_router
from app.observability_routes import router as observability_router
from app.hospital_intelligence_routes import router as hospital_intelligence_router
from app.bvs_v6_routes import router as bvs_v6_router
from app.bvs_v6_rota_routes import router as bvs_v6_rota_router
from app.v7_realtime_routes import router as v7_realtime_router
from app.v7_shadow_routes import router as v7_shadow_router
from app.v7_integration_retry_routes import router as v7_integration_retry_router
from app.clinical_execution_routes import router as clinical_execution_router
from app.clinical_execution_governance_routes import router as clinical_execution_governance_router
from app.clinical_execution_governance_dashboard_routes import router as clinical_execution_governance_dashboard_router
from app.detailed_hospital_routes import router as detailed_hospital_router
from app.detailed_hospital_completion_routes import router as detailed_hospital_completion_router
from app.hospital_command_routes import router as hospital_command_router
from app.hospital_command_intake_routes import router as hospital_command_intake_router
from app.compliance_safety_routes import router as compliance_safety_router
from app.compliance_safety_deployment_routes import router as compliance_safety_deployment_router
from app.hospital_master_board_v11_routes import router as hospital_master_board_v11_router
from app.referral_identity_v12_routes import router as referral_identity_v12_router
from app.medication_foundation_v18_routes import router as medication_foundation_v18_router
from app.speech_capture_v19_routes import router as speech_capture_v19_router
from app.operational_automation_v20_routes import router as operational_automation_v20_router
from app.recorded_state_automation_v21_routes import (
    generic_guard_router as recorded_state_automation_guard_v21_router,
    recorded_router as recorded_state_automation_v21_router,
)
from app import event_driven_automation_v22_concurrency_patch as _event_driven_automation_v22_concurrency_patch  # noqa: F401
from app.event_driven_automation_v22_routes import (
    generic_guard_router as event_driven_automation_guard_v22_router,
    router as event_driven_automation_v22_router,
)
from app.event_driven_automation_v22_runtime import install_event_driven_automation_v22
from app.automation_operator_control_v23_routes import router as automation_operator_control_v23_router
from app.pilot_control_v24_routes import (
    legacy_shadow_guard_router as pilot_control_legacy_shadow_guard_v24_router,
    router as pilot_control_v24_router,
)
from app.safety_bridge_v25_routes import router as safety_bridge_v25_router
from app.safety_control_v25_routes import router as safety_control_v25_router
from app import production_readiness_migration_head_v24_patch as _production_readiness_migration_head_v24_patch  # noqa: F401
from app import speech_capture_v19_serialization_patch as _speech_capture_v19_serialization_patch  # noqa: F401
from app import referral_identity_v12_serialization_patch as _referral_identity_v12_serialization_patch  # noqa: F401
from app import compliance_safety_evidence_patch as _compliance_safety_evidence_patch  # noqa: F401
from app import hospital_command_hardening as _hospital_command_hardening  # noqa: F401
from app import hospital_command_early_closure_patch as _hospital_command_early_closure_patch  # noqa: F401
from app import detailed_hospital_serialization_patch as _detailed_hospital_serialization_patch  # noqa: F401
from app import critical_result_deadline_patch as _critical_result_deadline_patch  # noqa: F401
from app import auth as auth_module

auth_module.PUBLIC_PATHS.add("/api/metrics")

app.add_middleware(VerifiedActorAttributionMiddlewareV25)
if os.getenv("LUCYWORKS_LEGACY_TEST_BYPASS", "false").lower() not in {"1", "true", "yes"}:
    app.add_middleware(VerifiedIdentityMiddleware)
app.add_middleware(LegacyWriteRetirementMiddleware)
app.add_middleware(ProductionProtectionMiddleware)

app.include_router(auth_router)
app.include_router(v3_operational_router)
app.include_router(ops_engine_router)
app.include_router(input_router)
app.include_router(department_router)
app.include_router(forecast_router)
app.include_router(readiness_router)
# Exact authenticated bridges must be registered before their legacy route modules.
app.include_router(safety_bridge_v25_router)
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
app.include_router(pilot_control_legacy_shadow_guard_v24_router)
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
app.include_router(integration_router)
app.include_router(hospital_ops_router)
app.include_router(hospital_ops_extension_router)
app.include_router(production_readiness_router)
app.include_router(pilot_control_v24_router)
app.include_router(safety_control_v25_router)
app.include_router(observability_router)
app.include_router(hospital_intelligence_router)
app.include_router(bvs_v6_router)
app.include_router(bvs_v6_rota_router)
app.include_router(v7_realtime_router)
app.include_router(v7_shadow_router)
app.include_router(v7_integration_retry_router)
app.include_router(clinical_execution_router)
app.include_router(clinical_execution_governance_router)
app.include_router(clinical_execution_governance_dashboard_router)
app.include_router(detailed_hospital_router)
app.include_router(detailed_hospital_completion_router)
app.include_router(hospital_command_router)
app.include_router(hospital_command_intake_router)
app.include_router(compliance_safety_router)
app.include_router(compliance_safety_deployment_router)
app.include_router(hospital_master_board_v11_router)
app.include_router(referral_identity_v12_router)
app.include_router(medication_foundation_v18_router)
app.include_router(speech_capture_v19_router)
app.include_router(event_driven_automation_guard_v22_router)
app.include_router(recorded_state_automation_guard_v21_router)
app.include_router(recorded_state_automation_v21_router)
app.include_router(event_driven_automation_v22_router)
app.include_router(automation_operator_control_v23_router)
app.include_router(operational_automation_v20_router)

install_event_driven_automation_v22(app)
