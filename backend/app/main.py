from app.main_fixed import app
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
