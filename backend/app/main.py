from app.main_fixed import app
from app.domain_routes import router as domain_router
from app.safety_routes import router as safety_router

app.include_router(domain_router)
app.include_router(safety_router)
