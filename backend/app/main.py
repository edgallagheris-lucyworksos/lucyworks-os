from app.main_fixed import app
from app.clinical_director_routes import router as clinical_director_router
from app.dashboard_routes import router as dashboard_router
from app.domain_routes import router as domain_router
from app.operating_routes import router as operating_router
from app.safety_routes import router as safety_router

app.include_router(domain_router)
app.include_router(operating_router)
app.include_router(dashboard_router)
app.include_router(clinical_director_router)
app.include_router(safety_router)
