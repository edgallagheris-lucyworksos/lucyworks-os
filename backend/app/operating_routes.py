from fastapi import APIRouter

from app.operating_catalogue import HOSPITAL_OPERATING_CATALOGUE

router = APIRouter()


@router.get("/api/operating-catalogue")
def operating_catalogue():
    return HOSPITAL_OPERATING_CATALOGUE


@router.get("/api/operating-catalogue/departments")
def operating_departments():
    return HOSPITAL_OPERATING_CATALOGUE["departments"]


@router.get("/api/operating-catalogue/procedures")
def operating_procedures():
    return HOSPITAL_OPERATING_CATALOGUE["procedure_templates"]


@router.get("/api/operating-catalogue/pharmacy-governance")
def operating_pharmacy_governance():
    return HOSPITAL_OPERATING_CATALOGUE["pharmacy_governance"]


@router.get("/api/operating-catalogue/compliance")
def operating_compliance():
    return {
        "legal_and_compliance_guardrails": HOSPITAL_OPERATING_CATALOGUE["legal_and_compliance_guardrails"],
        "operating_rules": HOSPITAL_OPERATING_CATALOGUE["operating_rules"],
    }
