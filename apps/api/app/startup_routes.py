from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.department_routes import seed_departments
from app.hospital_scale_seed import seed_hospital_scale

router = APIRouter()


@router.post("/api/admin/seed-hospital-scale")
def seed_hospital_scale_endpoint(session: Session = Depends(get_session)):
    seed_hospital_scale(session)
    return {"ok": True, "seeded": "hospital_scale"}


@router.post("/api/admin/first-run")
def first_run_endpoint(session: Session = Depends(get_session)):
    seed_hospital_scale(session)
    department_result = seed_departments(actor_name="First Run", session=session)
    return {
        "ok": True,
        "seeded": ["hospital_scale", "department_ops"],
        "department_result": department_result,
        "next": [
            "/system-control",
            "/readiness",
            "/departments",
            "/command",
            "/workspace",
            "/actions",
        ],
    }
