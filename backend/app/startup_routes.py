from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.hospital_scale_seed import seed_hospital_scale

router = APIRouter()


@router.post("/api/admin/seed-hospital-scale")
def seed_hospital_scale_endpoint(session: Session = Depends(get_session)):
    seed_hospital_scale(session)
    return {"ok": True, "seeded": "hospital_scale"}
