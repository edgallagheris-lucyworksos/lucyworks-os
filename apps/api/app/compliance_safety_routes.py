from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, require_roles
from app.compliance_safety_models import DeploymentProfileV10, SafetyCaseV10, SafetyHazardV10, SafetyReviewV10, utc_now
from app.database import get_session
from app.evidence_service import create_evidence_event

router = APIRouter(prefix="/api/v10/compliance-safety", tags=["compliance-safety-v10"])
READ_ROLES = ("admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor")
SENIOR_ROLES = ("admin", "clinical_director", "governance_lead", "hospital_director", "ops_manager", "senior_clinician", "supervisor")
APPROVAL_ROLES = ("clinical_director", "governance_lead", "hospital_director")
TARGETS = ("synthetic", "historical_replay", "shadow", "bounded_pilot", "live")


def ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def parse_json(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def baseline_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "compliance" / "uk-veterinary-compliance-safety-v10.json"


@lru_cache(maxsize=1)
def load_baseline() -> dict[str, Any]:
    path = baseline_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"compliance baseline missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"compliance baseline invalid: {exc}") from exc
    required = {"baselineId", "asOfDate", "sourceStatuses", "sources", "obligations", "identityGroups", "vendorContracts", "syntheticDataPacks", "dpia", "safetyMethodology"}
    missing = required - set(payload)
    if missing:
        raise RuntimeError(f"compliance baseline missing keys: {sorted(missing)}")
    return payload


HAZARDS: tuple[dict[str, Any], ...] = (
    {"code":"HZ-001","category":"identity","title":"Wrong patient or owner selected","situation":"An action is recorded against the wrong animal or client.","harm":"Wrong treatment, confidentiality breach, delayed care or incorrect billing.","severity":5,"likelihood":3,"controls":["two identifiers","episode-patient invariant","vendor crosswalk reconciliation","prominent patient banner"],"verification":["wrong-patient negative test","duplicate-name scenario"],"rs":5,"rl":1,"owner":"clinical_director","sources":["rcvs-code-vs","ico-dpia"]},
    {"code":"HZ-002","category":"concurrency","title":"Stale or duplicate command changes current state","situation":"Two users or integrations act on an outdated episode version.","harm":"Conflicting treatment, location or accountability state.","severity":5,"likelihood":3,"controls":["optimistic concurrency","row locking","idempotency","transition ledger"],"verification":["stale-write test","duplicate replay"],"rs":5,"rl":1,"owner":"ops_manager","sources":["SAFE-001"]},
    {"code":"HZ-003","category":"authority","title":"Unauthorised clinical action","situation":"A user without registration, competence or authority records or approves care.","harm":"Illegal or unsafe care.","severity":5,"likelihood":3,"controls":["verified identity","role gate","competency evidence","delegation boundary","audit"],"verification":["role denial","expired competency"],"rs":5,"rl":1,"owner":"clinical_director","sources":["rcvs-delegation","rcvs-team"]},
    {"code":"HZ-004","category":"consent","title":"Treatment without valid informed consent","situation":"Consent is missing, withdrawn, expired or captured from someone without authority.","harm":"Unauthorised treatment, client detriment or dispute.","severity":4,"likelihood":3,"controls":["decision authority","scoped consent","withdrawal history","phase gate"],"verification":["withdrawn-consent test","wrong-owner test"],"rs":4,"rl":1,"owner":"clinician","sources":["rcvs-consent"]},
    {"code":"HZ-005","category":"medication","title":"Wrong medicine, dose, weight or unit","situation":"An order uses stale weight, incompatible units, allergy or duplicate therapy.","harm":"Toxicity, treatment failure or death.","severity":5,"likelihood":3,"controls":["current weight","unit normalisation","allergy check","formulary rule","prescriber sign-off"],"verification":["mg-per-kg boundaries","stale weight","allergy"],"rs":5,"rl":2,"owner":"clinical_director","sources":["vmr-records"]},
    {"code":"HZ-006","category":"controlled_drugs","title":"Controlled-drug discrepancy hidden","situation":"Receipt, administration, wastage or destruction does not reconcile.","harm":"Diversion, legal breach or patient harm.","severity":5,"likelihood":2,"controls":["append-only ledger","running balance","witness","discrepancy alert"],"verification":["negative balance","missing witness"],"rs":5,"rl":1,"owner":"governance_lead","sources":["controlled-drugs"]},
    {"code":"HZ-007","category":"diagnostics","title":"Critical result not acknowledged","situation":"A critical imaging or laboratory result is delivered but not acted on.","harm":"Delayed treatment, deterioration or death.","severity":5,"likelihood":3,"controls":["critical flag","named acknowledgement","escalation timer","fallback contact"],"verification":["unacknowledged escalation","integration outage"],"rs":5,"rl":1,"owner":"clinical_director","sources":["rcvs-code-vs"]},
    {"code":"HZ-008","category":"handover","title":"Information lost during handover","situation":"Risks, pending actions or accountability are not received by the next team.","harm":"Missed or duplicated treatment and deterioration.","severity":5,"likelihood":3,"controls":["structured handover","receiving acknowledgement","pending actions","ownership changes after acknowledgement"],"verification":["open handover blocks transition","missing risk"],"rs":5,"rl":1,"owner":"nurse","sources":["rcvs-team"]},
    {"code":"HZ-009","category":"staffing","title":"Unsafe staffing or competency coverage","situation":"A service runs without required qualified staff, supervision or fatigue controls.","harm":"Delayed response, errors or inability to rescue a patient.","severity":5,"likelihood":3,"controls":["coverage requirements","competency matching","fatigue warning","service stop","escalation"],"verification":["coverage gap","expired registration"],"rs":5,"rl":2,"owner":"ops_manager","sources":["rcvs-emergency","defra-white-paper-2026"]},
    {"code":"HZ-010","category":"anaesthesia","title":"Anaesthesia state or monitoring incomplete","situation":"Procedure progresses without current charting, monitoring or recovery accountability.","harm":"Unrecognised deterioration, injury or death.","severity":5,"likelihood":3,"controls":["phase gate","observation interval","responsible clinician","recovery handover"],"verification":["missing chart blocks procedure","overdue observation"],"rs":5,"rl":1,"owner":"clinical_director","sources":["rcvs-delegation"]},
    {"code":"HZ-011","category":"discharge","title":"Unsafe or incomplete discharge","situation":"A patient leaves with unresolved concern, active plan, incomplete record or missing instructions.","harm":"Deterioration at home, medication error or failed follow-up.","severity":5,"likelihood":3,"controls":["discharge gate","sent-document evidence","owner communication","open-action check"],"verification":["active plan blocks discharge","unsent document"],"rs":5,"rl":1,"owner":"clinician","sources":["rcvs-code-vs"]},
    {"code":"HZ-012","category":"availability","title":"System outage hides current care information","situation":"Application, database or network failure prevents access to time-critical information.","harm":"Delayed or incorrect care.","severity":5,"likelihood":3,"controls":["high availability","backup and restore","downtime export","emergency procedure","monitoring"],"verification":["failure drill","restore rehearsal","downtime test"],"rs":5,"rl":2,"owner":"hospital_director","sources":["dcb0160"]},
    {"code":"HZ-013","category":"integration","title":"Vendor message duplicated, late or mismatched","situation":"External state overwrites newer canonical state or links to the wrong case.","harm":"Wrong clinical decision or missing result.","severity":5,"likelihood":3,"controls":["idempotency","event ordering","source provenance","crosswalk","reconciliation","no silent overwrite"],"verification":["out-of-order message","duplicate id","unmatched patient"],"rs":5,"rl":1,"owner":"ops_manager","sources":["SEC-001"]},
    {"code":"HZ-014","category":"privacy","title":"Client or staff information disclosed improperly","situation":"Excessive access, wrong recipient, insecure export or unjustified vendor disclosure.","harm":"Loss of confidentiality, distress, discrimination or enforcement.","severity":4,"likelihood":3,"controls":["least privilege","recipient confirmation","purpose logging","DPIA","processor contract"],"verification":["role access","wrong-recipient simulation"],"rs":4,"rl":1,"owner":"governance_lead","sources":["ico-dpia"]},
    {"code":"HZ-015","category":"ai","title":"AI output accepted as clinical fact","situation":"Generated text or recommendation is used without competent verification.","harm":"Incorrect diagnosis, treatment or record.","severity":5,"likelihood":3,"controls":["advisory label","manual verification","source display","no autonomous transition"],"verification":["unverified output cannot finalise","prompt injection"],"rs":5,"rl":1,"owner":"clinical_director","sources":["rcvs-ai-2026"]},
    {"code":"HZ-016","category":"consumer","title":"Cost or treatment information misleading or late","situation":"Estimate, variance, options, ownership or conflicts are incomplete.","harm":"Financial detriment or loss of informed choice.","severity":3,"likelihood":4,"controls":["written estimate","variance alert","itemised bill","options","conflict disclosure"],"verification":["£500 threshold","20 percent or £500 update"],"rs":3,"rl":1,"owner":"governance_lead","sources":["cma-final-2026"]},
    {"code":"HZ-017","category":"audit","title":"Material history deleted or altered","situation":"Clinical, medicine, consent, estimate or decision history is overwritten without trace.","harm":"Unsafe care, failed inspection, fraud or failed investigation.","severity":5,"likelihood":2,"controls":["append-only evidence","versions","database permissions","backup"],"verification":["attribution test","deletion denial","restore comparison"],"rs":5,"rl":1,"owner":"governance_lead","sources":["vmr-records","rcvs-code-vs"]},
    {"code":"HZ-018","category":"override","title":"Emergency override misused or left active","situation":"A gate is bypassed without urgency, expiry, review or corrective action.","harm":"Unsafe care or normalisation of deviance.","severity":5,"likelihood":2,"controls":["non-waivable gates","senior identity","reason","24-hour expiry","review"],"verification":["expired waiver","non-waivable gate"],"rs":5,"rl":1,"owner":"clinical_director","sources":["SAFE-001"]},
    {"code":"HZ-019","category":"time","title":"Clock or timezone error reorders care","situation":"Naive timestamps or daylight-saving conversion changes event order.","harm":"Missed dose, stale consent or incorrect audit sequence.","severity":4,"likelihood":3,"controls":["UTC storage","timezone-aware display","event sequence","clock monitoring"],"verification":["BST transition","naive timestamp normalisation"],"rs":4,"rl":1,"owner":"admin","sources":["SAFE-001"]},
)


class HazardUpdate(BaseModel):
    expectedVersion: int
    status: str
    residualSeverity: int = PydanticField(ge=1, le=5)
    residualLikelihood: int = PydanticField(ge=1, le=5)
    controls: list[str] = PydanticField(default_factory=list)
    verification: list[str] = PydanticField(default_factory=list)
    evidenceRefs: list[str] = PydanticField(default_factory=list)
    reason: str


class ReviewCreate(BaseModel):
    safetyCaseRef: str
    reviewType: str
    target: str
    outcome: str
    findings: list[dict[str, Any]] = PydanticField(default_factory=list)
    reason: str


class DeploymentUpdate(BaseModel):
    expectedVersion: int
    target: str
    dataMode: str
    identityMode: str
    vendorMode: str
    realIdentityConfirmed: bool = False
    realDataGovernanceConfirmed: bool = False
    realVendorConnectionsConfirmed: bool = False
    clinicalSafetyOfficerConfirmed: bool = False
    dpiaApproved: bool = False
    penetrationTestConfirmed: bool = False
    staffUatConfirmed: bool = False
    reason: str


def case_dict(row: SafetyCaseV10) -> dict[str, Any]:
    return {"safetyCaseRef":row.safety_case_ref,"title":row.title,"scope":row.scope,"releaseVersion":row.release_version,"methodology":row.methodology,"status":row.status,"safetyOwnerRole":row.safety_owner_role,"clinicalOwnerRole":row.clinical_owner_role,"safetyStatement":row.safety_statement,"limitations":parse_json(row.limitations_json, []),"generatedFromBaseline":row.generated_from_baseline,"approvedForTarget":row.approved_for_target,"approvedBy":{"subject":row.approved_by_subject,"name":row.approved_by_name},"approvedAt":row.approved_at.isoformat() if row.approved_at else None,"version":row.version,"updatedAt":row.updated_at.isoformat()}


def hazard_dict(row: SafetyHazardV10) -> dict[str, Any]:
    return {"hazardRef":row.hazard_ref,"safetyCaseRef":row.safety_case_ref,"code":row.code,"category":row.category,"title":row.title,"hazardousSituation":row.hazardous_situation,"potentialHarm":row.potential_harm,"severity":row.severity,"likelihood":row.likelihood,"initialRisk":row.initial_risk,"controls":parse_json(row.controls_json, []),"verification":parse_json(row.verification_json, []),"evidenceRefs":parse_json(row.evidence_refs_json, []),"residualSeverity":row.residual_severity,"residualLikelihood":row.residual_likelihood,"residualRisk":row.residual_risk,"status":row.status,"ownerRole":row.owner_role,"sourceIds":parse_json(row.source_ids_json, []),"version":row.version,"updatedAt":row.updated_at.isoformat()}


def profile_dict(row: DeploymentProfileV10) -> dict[str, Any]:
    return {"profileRef":row.profile_ref,"environmentName":row.environment_name,"target":row.target,"dataMode":row.data_mode,"identityMode":row.identity_mode,"vendorMode":row.vendor_mode,"realIdentityConfirmed":row.real_identity_confirmed,"realDataGovernanceConfirmed":row.real_data_governance_confirmed,"realVendorConnectionsConfirmed":row.real_vendor_connections_confirmed,"clinicalSafetyOfficerConfirmed":row.clinical_safety_officer_confirmed,"dpiaApproved":row.dpi_a_approved,"penetrationTestConfirmed":row.penetration_test_confirmed,"staffUatConfirmed":row.staff_uat_confirmed,"blockers":parse_json(row.blockers_json, []),"status":row.status,"version":row.version,"updatedAt":row.updated_at.isoformat()}


def record_event(session: Session, auth: AuthContext, action: str, entity_type: str, entity_id: str, before: Any, after: Any, reason: str, risk: str = "amber") -> None:
    create_evidence_event(session,event_type="compliance_safety_v10",action=action,actor_id=auth.actor_id or auth.subject,actor_name=auth.actor_name,actor_role=auth.role,actor_auth_source=auth.auth_source,previous_state=before,new_state=after,reason=reason,justification="UK veterinary compliance and safety assurance",compliance_domain="clinical_safety",risk_level=risk,source_module="compliance_safety_v10",source_record_ref=entity_id,entity_type=entity_type,entity_id=entity_id)


def seed(session: Session, auth: AuthContext) -> tuple[SafetyCaseV10, list[SafetyHazardV10], DeploymentProfileV10]:
    baseline = load_baseline()
    case = session.exec(select(SafetyCaseV10).where(SafetyCaseV10.release_version == "v10")).first()
    if not case:
        case = SafetyCaseV10(safety_case_ref=ref("safety-case"),title="LucyWorks OS veterinary clinical and operational safety case v10",scope="Referral hospital operating system from intake to closure, including records, medicines, staffing, integrations, AI-assisted documentation and governance.",release_version="v10",methodology=baseline["safetyMethodology"]["basis"],safety_statement="The implemented controls reduce identified software-related clinical and operational risks for synthetic validation. Qualified professionals retain clinical judgement and deployment organisations retain responsibility for local use.",limitations_json=json_text(["No BVS identity directory, live patient data or vendor endpoints are claimed.","No external clinical safety officer, DPO, penetration tester or hospital executive has approved live use.","CMA remedies are implemented as future-ready controls while the July 2026 Order remains draft."]),generated_from_baseline=baseline["baselineId"],created_by_subject=auth.subject)
        session.add(case)
        session.flush()
    existing = {row.code:row for row in session.exec(select(SafetyHazardV10).where(SafetyHazardV10.safety_case_ref == case.safety_case_ref)).all()}
    hazards: list[SafetyHazardV10] = []
    for item in HAZARDS:
        row = existing.get(item["code"])
        if not row:
            row = SafetyHazardV10(hazard_ref=ref("hazard"),safety_case_ref=case.safety_case_ref,code=item["code"],category=item["category"],title=item["title"],hazardous_situation=item["situation"],potential_harm=item["harm"],severity=item["severity"],likelihood=item["likelihood"],initial_risk=item["severity"]*item["likelihood"],controls_json=json_text(item["controls"]),verification_json=json_text(item["verification"]),residual_severity=item["rs"],residual_likelihood=item["rl"],residual_risk=item["rs"]*item["rl"],status="controlled_by_design",owner_role=item["owner"],source_ids_json=json_text(item["sources"]))
            session.add(row)
        hazards.append(row)
    profile = session.exec(select(DeploymentProfileV10).where(DeploymentProfileV10.environment_name == "reference-synthetic-hospital")).first()
    if not profile:
        profile = DeploymentProfileV10(profile_ref=ref("deployment"),environment_name="reference-synthetic-hospital",target="synthetic",data_mode="synthetic",identity_mode="reference_groups",vendor_mode="contract_stubs",status="synthetic_ready",created_by_subject=auth.subject)
        session.add(profile)
    session.flush()
    return case, hazards, profile


def release_gate(session: Session, target: str, case: SafetyCaseV10 | None = None, profile: DeploymentProfileV10 | None = None) -> dict[str, Any]:
    if target not in TARGETS:
        raise HTTPException(status_code=400, detail="invalid release target")
    case = case or session.exec(select(SafetyCaseV10).order_by(SafetyCaseV10.created_at.desc())).first()
    profile = profile or session.exec(select(DeploymentProfileV10).order_by(DeploymentProfileV10.created_at.desc())).first()
    hazards = session.exec(select(SafetyHazardV10).where(SafetyHazardV10.safety_case_ref == case.safety_case_ref)).all() if case else []
    blockers: list[dict[str,str]] = []
    if not case:
        blockers.append({"code":"safety_case_missing","detail":"Safety baseline has not been bootstrapped."})
    if len(hazards) < len(HAZARDS):
        blockers.append({"code":"hazard_log_incomplete","detail":"The complete baseline hazard log is not present."})
    for row in hazards:
        if row.residual_risk >= 16 or row.status in {"open","uncontrolled","rejected"}:
            blockers.append({"code":row.code,"detail":f"{row.title}: residual risk {row.residual_risk} / status {row.status}"})
    if not profile:
        blockers.append({"code":"deployment_profile_missing","detail":"No deployment profile exists."})
    elif target in {"shadow","bounded_pilot","live"}:
        checks = {
            "real_identity": profile.real_identity_confirmed,
            "data_governance": profile.real_data_governance_confirmed,
            "vendor_connections": profile.real_vendor_connections_confirmed,
            "clinical_safety_officer": profile.clinical_safety_officer_confirmed,
            "dpia_approval": profile.dpi_a_approved,
        }
        if target in {"bounded_pilot","live"}:
            checks.update({"penetration_test":profile.penetration_test_confirmed,"staff_uat":profile.staff_uat_confirmed})
        blockers.extend({"code":key,"detail":f"Deployment organisation confirmation required for {key.replace('_',' ')}."} for key,value in checks.items() if not value)
    return {"target":target,"canRelease":not blockers,"blockers":blockers,"hazardCount":len(hazards),"highestResidualRisk":max((row.residual_risk for row in hazards),default=None),"boundary":"Synthetic and historical validation can be completed without BVS data. Shadow, pilot and live targets require accountable deployment-organisation confirmations."}


@router.post("/bootstrap")
def bootstrap(session: Session=Depends(get_session),auth:AuthContext=Depends(require_roles(*SENIOR_ROLES))) -> dict[str,Any]:
    case,hazards,profile=seed(session,auth); session.commit(); return {"safetyCase":case_dict(case),"hazards":len(hazards),"deploymentProfile":profile_dict(profile),"syntheticGate":release_gate(session,"synthetic",case,profile)}


@router.get("/baseline")
def baseline(status:str|None=Query(default=None),domain:str|None=Query(default=None),q:str|None=Query(default=None,min_length=2,max_length=100),_:AuthContext=Depends(require_roles(*READ_ROLES))) -> dict[str,Any]:
    payload=load_baseline(); obligations=payload["obligations"]
    if status: obligations=[row for row in obligations if row["status"]==status]
    if domain: obligations=[row for row in obligations if row["domain"]==domain]
    if q: obligations=[row for row in obligations if q.casefold() in json.dumps(row).casefold()]
    return {**payload,"obligations":obligations}


@router.get("/summary")
def summary(session:Session=Depends(get_session),_:AuthContext=Depends(require_roles(*READ_ROLES))) -> dict[str,Any]:
    baseline=load_baseline(); case=session.exec(select(SafetyCaseV10).order_by(SafetyCaseV10.created_at.desc())).first(); profile=session.exec(select(DeploymentProfileV10).order_by(DeploymentProfileV10.created_at.desc())).first(); hazards=session.exec(select(SafetyHazardV10)).all()
    return {"baselineId":baseline["baselineId"],"asOfDate":baseline["asOfDate"],"sources":len(baseline["sources"]),"obligations":len(baseline["obligations"]),"identityGroups":len(baseline["identityGroups"]),"vendorContracts":len(baseline["vendorContracts"]),"syntheticPacks":len(baseline["syntheticDataPacks"]),"safetyCase":case_dict(case) if case else None,"deploymentProfile":profile_dict(profile) if profile else None,"hazards":{"total":len(hazards),"open":len([h for h in hazards if h.status in {"open","uncontrolled"}]),"highResidual":len([h for h in hazards if h.residual_risk>=16])},"gates":{target:release_gate(session,target,case,profile) for target in TARGETS}}


@router.get("/safety-case")
def get_safety_case(session:Session=Depends(get_session),_:AuthContext=Depends(require_roles(*READ_ROLES))) -> dict[str,Any]:
    case=session.exec(select(SafetyCaseV10).order_by(SafetyCaseV10.created_at.desc())).first()
    if not case: raise HTTPException(status_code=404,detail="safety case not bootstrapped")
    hazards=session.exec(select(SafetyHazardV10).where(SafetyHazardV10.safety_case_ref==case.safety_case_ref).order_by(SafetyHazardV10.code)).all(); reviews=session.exec(select(SafetyReviewV10).where(SafetyReviewV10.safety_case_ref==case.safety_case_ref).order_by(SafetyReviewV10.created_at.desc())).all()
    return {"safetyCase":case_dict(case),"hazards":[hazard_dict(row) for row in hazards],"reviews":[{"reviewRef":r.review_ref,"reviewType":r.review_type,"target":r.target,"outcome":r.outcome,"findings":parse_json(r.findings_json,[]),"reason":r.reason,"reviewer":{"subject":r.reviewer_subject,"name":r.reviewer_name,"role":r.reviewer_role},"createdAt":r.created_at.isoformat()} for r in reviews]}


@router.patch("/hazards/{hazard_ref}")
def update_hazard(hazard_ref:str,payload:HazardUpdate,session:Session=Depends(get_session),auth:AuthContext=Depends(require_roles(*SENIOR_ROLES))) -> dict[str,Any]:
    row=session.exec(select(SafetyHazardV10).where(SafetyHazardV10.hazard_ref==hazard_ref).with_for_update()).first()
    if not row: raise HTTPException(status_code=404,detail="hazard not found")
    if row.version!=payload.expectedVersion: raise HTTPException(status_code=409,detail={"message":"stale hazard","currentVersion":row.version})
    if payload.status not in {"open","controlled_by_design","verified","accepted_for_target","uncontrolled","rejected"}: raise HTTPException(status_code=422,detail="invalid hazard status")
    residual=payload.residualSeverity*payload.residualLikelihood
    if residual>=16 and payload.status in {"controlled_by_design","verified","accepted_for_target"}: raise HTTPException(status_code=409,detail="risk 16 or above cannot be marked controlled or accepted")
    before=hazard_dict(row); row.status=payload.status; row.residual_severity=payload.residualSeverity; row.residual_likelihood=payload.residualLikelihood; row.residual_risk=residual; row.controls_json=json_text(payload.controls); row.verification_json=json_text(payload.verification); row.evidence_refs_json=json_text(payload.evidenceRefs); row.version+=1; row.updated_at=utc_now(); session.add(row); after=hazard_dict(row); record_event(session,auth,"hazard updated","safety_hazard",row.hazard_ref,before,after,payload.reason,"red" if residual>=16 else "amber" if residual>=10 else "green"); session.commit(); session.refresh(row); return {"hazard":hazard_dict(row)}


@router.get("/deployment-profile")
def get_profile(session:Session=Depends(get_session),_:AuthContext=Depends(require_roles(*READ_ROLES))) -> dict[str,Any]:
    row=session.exec(select(DeploymentProfileV10).order_by(DeploymentProfileV10.created_at.desc())).first()
    if not row: raise HTTPException(status_code=404,detail="deployment profile not bootstrapped")
    return {"deploymentProfile":profile_dict(row),"gates":{target:release_gate(session,target,profile=row) for target in TARGETS}}


@router.patch("/deployment-profile/{profile_ref}")
def update_profile(profile_ref:str,payload:DeploymentUpdate,session:Session=Depends(get_session),auth:AuthContext=Depends(require_roles(*APPROVAL_ROLES))) -> dict[str,Any]:
    row=session.exec(select(DeploymentProfileV10).where(DeploymentProfileV10.profile_ref==profile_ref).with_for_update()).first()
    if not row: raise HTTPException(status_code=404,detail="deployment profile not found")
    if row.version!=payload.expectedVersion: raise HTTPException(status_code=409,detail={"message":"stale deployment profile","currentVersion":row.version})
    if payload.target not in TARGETS: raise HTTPException(status_code=422,detail="invalid target")
    before=profile_dict(row); row.target=payload.target; row.data_mode=payload.dataMode; row.identity_mode=payload.identityMode; row.vendor_mode=payload.vendorMode; row.real_identity_confirmed=payload.realIdentityConfirmed; row.real_data_governance_confirmed=payload.realDataGovernanceConfirmed; row.real_vendor_connections_confirmed=payload.realVendorConnectionsConfirmed; row.clinical_safety_officer_confirmed=payload.clinicalSafetyOfficerConfirmed; row.dpi_a_approved=payload.dpiaApproved; row.penetration_test_confirmed=payload.penetrationTestConfirmed; row.staff_uat_confirmed=payload.staffUatConfirmed; gate=release_gate(session,payload.target,profile=row); row.blockers_json=json_text(gate["blockers"]); row.status="ready" if gate["canRelease"] else "blocked"; row.version+=1; row.updated_at=utc_now(); session.add(row); after=profile_dict(row); record_event(session,auth,"deployment profile updated","deployment_profile",row.profile_ref,before,after,payload.reason,"green" if gate["canRelease"] else "amber"); session.commit(); session.refresh(row); return {"deploymentProfile":profile_dict(row),"gate":release_gate(session,row.target,profile=row)}


@router.post("/reviews")
def create_review(payload:ReviewCreate,session:Session=Depends(get_session),auth:AuthContext=Depends(require_roles(*APPROVAL_ROLES))) -> dict[str,Any]:
    if payload.target not in TARGETS: raise HTTPException(status_code=422,detail="invalid target")
    if payload.outcome not in {"approved","approved_with_conditions","changes_required","rejected","developer_baseline_review"}: raise HTTPException(status_code=422,detail="invalid outcome")
    case=session.exec(select(SafetyCaseV10).where(SafetyCaseV10.safety_case_ref==payload.safetyCaseRef).with_for_update()).first()
    if not case: raise HTTPException(status_code=404,detail="safety case not found")
    gate=release_gate(session,payload.target,case=case)
    if payload.outcome.startswith("approved") and not gate["canRelease"]: raise HTTPException(status_code=409,detail={"message":"release gate blocked","blockers":gate["blockers"]})
    row=SafetyReviewV10(review_ref=ref("safety-review"),safety_case_ref=case.safety_case_ref,review_type=payload.reviewType,target=payload.target,outcome=payload.outcome,findings_json=json_text(payload.findings),reason=payload.reason,reviewer_subject=auth.subject,reviewer_name=auth.actor_name,reviewer_role=auth.role); session.add(row)
    if payload.outcome.startswith("approved"):
        case.status="approved_for_target"; case.approved_for_target=payload.target; case.approved_by_subject=auth.subject; case.approved_by_name=auth.actor_name; case.approved_at=utc_now(); case.version+=1; case.updated_at=utc_now(); session.add(case)
    record_event(session,auth,"safety review recorded","safety_case",case.safety_case_ref,None,{"reviewRef":row.review_ref,"target":payload.target,"outcome":payload.outcome,"gate":gate},payload.reason,"green" if payload.outcome.startswith("approved") else "amber"); session.commit(); return {"review":{"reviewRef":row.review_ref,"target":row.target,"outcome":row.outcome,"reviewerRole":row.reviewer_role},"safetyCase":case_dict(case),"gate":gate}


@router.get("/release-gate")
def get_release_gate(target:str=Query(default="synthetic"),session:Session=Depends(get_session),_:AuthContext=Depends(require_roles(*READ_ROLES))) -> dict[str,Any]:
    return release_gate(session,target)
