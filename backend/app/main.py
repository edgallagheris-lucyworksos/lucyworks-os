from app.main_fixed import app
from app.domain_routes import router as domain_router

app.include_router(domain_router)
