import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_v27_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "organisation-onboarding-v27-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-v27-smoke",
    "AUTH_AUDIENCE": "lucyworks-v27-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
    "V26_CONTEXT_BOOTSTRAP_ENABLED": "true",
    "V27_CONFIGURATION_REQUIRED": "false",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.bvs_v6_models import HospitalConfigurationRecord, WorkforceProfile
from app.clinical_execution_models import MedicationAdministration, MedicationOrder
from app.database import engine
from app.evidence_service import verify_event_chain
from app.hospital_command_models import EpisodeClosureV9, EpisodeTransitionV9
from app.models import User
from app.operational_context_v26_models import SiteMembershipV26, SiteV26
from app.organisation_onboarding_v27_models import (
    ConfigurationReleaseV27,
    OnboardingSiteV27,
    StaffAccessApprovalV27,
    StaffImportBatchV27,
)
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    session.add_all([
        User(id=2701, name="V27 Hospital Director", role="hospital_director", email="director-v27@example.test"),
        User(id=2702, name="V27 Clinician", role="clinician", email="clinician-v27@example.test"),
        User(id=2703, name="V27 Reception", role="reception", email="reception-v27@example.test"),
    ])
    session.commit()


def login(client: TestClient, user_id: int) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    token = response.json().get("accessToken")
    assert token
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def ok(response, label: str):
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    return response.json()


def post_payload(client: TestClient, path: str, headers: dict[str, str], payload: dict, label: str):
    return ok(client.post(path, headers=headers, json={"payload": payload}), label)


try:
    with TestClient(app) as client:
        director = login(client, 2701)
        clinician = login(client, 2702)
        reception = login(client, 2703)

        contracts = ok(client.get("/api/v27/contracts", headers=director), "load v27 contracts")
        assert contracts["authorityBoundary"]["draftDataAffectsOperations"] is False
        assert contracts["authorityBoundary"]["importedRoleGrantsAccess"] is False

        post_payload(client, "/api/v27/organisations", director, {
            "organisationRef": "referral-group-v27",
            "legalName": "Referral Group V27 Limited",
            "tradingName": "Referral Group V27",
            "companyNumber": "12345678",
            "countryCode": "GB",
            "registeredAddress": {"line1": "1 Clinical Way", "city": "Bristol", "postcode": "BS1 1AA"},
            "dataControllerName": "V27 Data Controller",
            "dataControllerEmail": "data-v27@example.test",
            "accountableExecutiveSubject": "local-user:2701",
            "accountableExecutiveName": "V27 Hospital Director",
            "reason": "Create the legal organisation onboarding record.",
        }, "create organisation")
        post_payload(client, "/api/v27/sites", director, {
            "siteRef": "referral-hospital-v27",
            "organisationRef": "referral-group-v27",
            "premisesRef": "premises-v27-bristol",
            "name": "Referral Hospital V27",
            "siteType": "referral_hospital",
            "timezone": "Europe/London",
            "address": {"line1": "2 Hospital Way", "city": "Bristol", "postcode": "BS2 2BB"},
            "regulatorPremisesRefs": ["RCVS-PREM-V27"],
            "accountableDirectorSubject": "local-user:2701",
            "accountableDirectorName": "V27 Hospital Director",
            "clinicalGovernanceSubject": "local-user:2702",
            "clinicalGovernanceName": "V27 Clinician",
            "reason": "Create a governed referral hospital site.",
        }, "create site")

        with Session(engine) as session:
            assert not session.exec(select(SiteV26).where(SiteV26.site_ref == "referral-hospital-v27")).first()
            assert not session.exec(select(HospitalConfigurationRecord).where(
                HospitalConfigurationRecord.premises_ref == "premises-v27-bristol"
            )).all()

        post_payload(client, "/api/v27/departments", director, {
            "siteRef": "referral-hospital-v27",
            "departmentRef": "diagnostic-imaging",
            "name": "Diagnostic Imaging",
            "departmentType": "clinical",
            "accountableRole": "clinical_director",
            "accountableSubject": "local-user:2702",
            "status": "verified",
            "reason": "Configure imaging accountability.",
        }, "create department")
        post_payload(client, "/api/v27/services", director, {
            "siteRef": "referral-hospital-v27",
            "serviceRef": "mri",
            "departmentRef": "diagnostic-imaging",
            "name": "MRI",
            "serviceType": "diagnostic_imaging",
            "clinicalService": True,
            "operationalStatus": "verified",
            "hours": {"monday": ["08:00", "20:00"]},
            "capabilities": ["small_animal_mri"],
            "minimumStaffing": [
                {"role": "clinician", "minimum": 1},
                {"role": "nurse", "minimum": 1},
            ],
            "requiredEquipmentRefs": ["mri-scanner-1"],
            "escalationRole": "clinical_director",
            "reason": "Configure MRI service controls.",
        }, "create service")
        post_payload(client, "/api/v27/rooms", director, {
            "siteRef": "referral-hospital-v27",
            "roomRef": "mri-suite-1",
            "departmentRef": "diagnostic-imaging",
            "name": "MRI Suite 1",
            "roomType": "mri_suite",
            "serviceRefs": ["mri"],
            "infectionControlZone": "controlled",
            "capacity": 1,
            "operationalStatus": "verified",
            "attributes": {"oxygen": True, "anaestheticMachine": True},
            "reason": "Map the MRI clinical room.",
        }, "create room")
        post_payload(client, "/api/v27/equipment", director, {
            "siteRef": "referral-hospital-v27",
            "equipmentRef": "mri-scanner-1",
            "name": "MRI Scanner 1",
            "equipmentType": "mri_scanner",
            "roomRef": "mri-suite-1",
            "serviceRefs": ["mri"],
            "assetIdentifier": "ASSET-MRI-V27",
            "maintenanceStatus": "verified",
            "maintenanceDueAt": (date.today() + timedelta(days=180)).isoformat(),
            "operationalStatus": "verified",
            "reason": "Record verified MRI equipment and maintenance.",
        }, "create equipment")

        required_policies = {
            "fatigue_and_safe_staffing": {"maximumWeeklyHours": 48, "escalationRole": "ops_manager"},
            "patient_safety_escalation": {"redResponseMinutes": 15, "ownerRole": "clinical_director"},
            "service_restriction": {"namedDecisionRequired": True},
            "safeguarding": {"confidentialRoute": True},
            "data_retention": {"retentionScheduleRef": "RET-V27"},
            "downtime_and_recovery": {"paperFallback": True, "reconciliationRequired": True},
        }
        for key, rules in required_policies.items():
            post_payload(client, "/api/v27/policies", director, {
                "siteRef": "referral-hospital-v27",
                "policyKey": key,
                "title": key.replace("_", " ").title(),
                "policyVersion": "1.0",
                "status": "approved",
                "rules": rules,
                "ownerRole": "governance_lead",
                "ownerSubject": "local-user:2701",
                "effectiveFrom": date.today().isoformat(),
                "reviewDueAt": (date.today() + timedelta(days=365)).isoformat(),
                "evidenceRefs": [f"policy-evidence:{key}"],
                "reason": f"Approve {key} for configuration release.",
            }, f"create policy {key}")

        bad_preview = ok(client.post("/api/v27/staff/imports/preview", headers=director, json={
            "siteRef": "referral-hospital-v27",
            "sourceType": "csv",
            "sourceRef": "bad-staff-v27.csv",
            "rows": [{"staffRef": "missing-name", "departmentRef": "diagnostic-imaging"}],
            "reason": "Prove invalid workforce data cannot be committed.",
        }), "preview invalid staff import")
        assert bad_preview["batch"]["errorCount"] == 1
        blocked_commit = client.post(
            f"/api/v27/staff/imports/{bad_preview['batch']['batchRef']}/commit",
            headers=director,
            json={"reason": "Invalid import must remain blocked."},
        )
        assert blocked_commit.status_code == 409, blocked_commit.text

        valid_preview = ok(client.post("/api/v27/staff/imports/preview", headers=director, json={
            "siteRef": "referral-hospital-v27",
            "sourceType": "csv",
            "sourceRef": "staff-v27.csv",
            "rows": [
                {
                    "staffRef": "staff-director-v27",
                    "displayName": "V27 Hospital Director",
                    "email": "director-v27@example.test",
                    "authSubject": "local-user:2701",
                    "departmentRef": "diagnostic-imaging",
                    "requestedRole": "hospital_director",
                    "primaryRoleRef": "hospital_director",
                    "contractedHoursWeekly": 40,
                    "maximumSafeHoursWeekly": 48,
                },
                {
                    "staffRef": "staff-clinician-v27",
                    "displayName": "V27 Clinician",
                    "email": "clinician-v27@example.test",
                    "authSubject": "local-user:2702",
                    "departmentRef": "diagnostic-imaging",
                    "requestedRole": "clinician",
                    "primaryRoleRef": "veterinary_surgeon",
                    "contractedHoursWeekly": 40,
                    "maximumSafeHoursWeekly": 48,
                },
                {
                    "staffRef": "staff-reception-v27",
                    "displayName": "V27 Reception",
                    "email": "reception-v27@example.test",
                    "authSubject": "local-user:2703",
                    "departmentRef": "diagnostic-imaging",
                    "requestedRole": "reception",
                    "primaryRoleRef": "reception",
                    "contractedHoursWeekly": 37.5,
                    "maximumSafeHoursWeekly": 48,
                },
            ],
            "reason": "Preview the workforce import without granting access.",
        }), "preview valid staff import")
        assert valid_preview["batch"]["errorCount"] == 0
        committed = ok(client.post(
            f"/api/v27/staff/imports/{valid_preview['batch']['batchRef']}/commit",
            headers=director,
            json={"reason": "Commit validated staff records as onboarding data only."},
        ), "commit staff import")
        assert all(row["accessStatus"] == "not_requested" for row in committed["staff"])
        assert all(row["identityStatus"] == "pending_match" for row in committed["staff"])

        with Session(engine) as session:
            assert not session.exec(select(SiteMembershipV26).where(
                SiteMembershipV26.site_ref == "referral-hospital-v27"
            )).all()

        readiness = ok(client.get(
            "/api/v27/readiness?siteRef=referral-hospital-v27", headers=director
        ), "load configuration readiness")
        assert readiness["configurationReady"] is True, readiness
        assert readiness["goLiveReady"] is False
        assert readiness["accessBlockers"]

        release_one = ok(client.post(
            "/api/v27/sites/referral-hospital-v27/releases/approve",
            headers=director,
            json={"reason": "Approve the first complete hospital configuration release."},
        ), "approve first release")["release"]
        assert release_one["releaseVersion"] == 1

        with Session(engine) as session:
            runtime_site = session.exec(select(SiteV26).where(SiteV26.site_ref == "referral-hospital-v27")).one()
            assert runtime_site.configuration_state == "approved_v27"
            runtime_room = session.exec(select(HospitalConfigurationRecord).where(
                HospitalConfigurationRecord.premises_ref == "premises-v27-bristol",
                HospitalConfigurationRecord.entity_type == "room",
                HospitalConfigurationRecord.entity_ref == "mri-suite-1",
            )).one()
            assert runtime_room.name == "MRI Suite 1"
            assert session.exec(select(WorkforceProfile).where(
                WorkforceProfile.premises_ref == "premises-v27-bristol"
            )).all()

        os.environ["V27_CONFIGURATION_REQUIRED"] = "true"
        no_access = client.get("/api/v26/context", headers=clinician)
        assert no_access.status_code == 403, no_access.text

        for staff_ref, subject in (
            ("staff-director-v27", "local-user:2701"),
            ("staff-clinician-v27", "local-user:2702"),
            ("staff-reception-v27", "local-user:2703"),
        ):
            ok(client.post(
                f"/api/v27/sites/referral-hospital-v27/staff/{staff_ref}/identity",
                headers=director,
                json={"authSubject": subject, "reason": "Independently match the staff identity to the authenticated subject."},
            ), f"verify identity {staff_ref}")

        clinical_access_blocked = client.post(
            "/api/v27/sites/referral-hospital-v27/staff/staff-clinician-v27/approve-access",
            headers=director,
            json={"reason": "Clinical access must fail without professional evidence.", "evidenceRefs": ["access-review-v27"]},
        )
        assert clinical_access_blocked.status_code == 409, clinical_access_blocked.text

        post_payload(client, "/api/v27/sites/referral-hospital-v27/staff/staff-clinician-v27/credentials", director, {
            "credentialType": "professional_registration",
            "issuingBody": "RCVS",
            "credentialNumber": "RCVS-V27-001",
            "validFrom": date.today().isoformat(),
            "validUntil": (date.today() + timedelta(days=365)).isoformat(),
            "verificationStatus": "verified",
            "evidenceRefs": ["rcvs-register-check-v27"],
            "reason": "Verify current professional registration.",
        }, "verify clinical credential")
        post_payload(client, "/api/v27/sites/referral-hospital-v27/staff/staff-clinician-v27/competencies", director, {
            "competencyRef": "mri_case_management",
            "scopeRef": "mri",
            "level": "independent",
            "verificationStatus": "verified",
            "evidenceSummary": "Clinical director reviewed training and recent case evidence.",
            "evidenceRefs": ["competency-review-v27"],
            "validFrom": date.today().isoformat(),
            "validUntil": (date.today() + timedelta(days=365)).isoformat(),
            "reason": "Verify MRI case-management competency.",
        }, "verify clinical competency")

        for staff_ref in ("staff-director-v27", "staff-clinician-v27", "staff-reception-v27"):
            approval = ok(client.post(
                f"/api/v27/sites/referral-hospital-v27/staff/{staff_ref}/approve-access",
                headers=director,
                json={"reason": "Approve the independently reviewed hospital access role.", "evidenceRefs": [f"access-review:{staff_ref}"]},
            ), f"approve access {staff_ref}")
            assert approval["approval"]["status"] == "approved"

        director_context = ok(client.get("/api/v26/context", headers=director), "load director governed context")
        clinician_context = ok(client.get("/api/v26/context", headers=clinician), "load clinician governed context")
        reception_context = ok(client.get("/api/v26/context", headers=reception), "load reception governed context")
        assert director_context["context"]["siteRef"] == "referral-hospital-v27"
        assert clinician_context["sites"][0]["role"] == "clinician"
        assert reception_context["sites"][0]["role"] == "reception"

        readiness_after_access = ok(client.get(
            "/api/v27/readiness?siteRef=referral-hospital-v27", headers=director
        ), "load go-live readiness")
        assert readiness_after_access["goLiveReady"] is True, readiness_after_access

        post_payload(client, "/api/v27/rooms", director, {
            "siteRef": "referral-hospital-v27",
            "roomRef": "mri-suite-1",
            "departmentRef": "diagnostic-imaging",
            "name": "MRI Suite Renamed Draft",
            "roomType": "mri_suite",
            "serviceRefs": ["mri"],
            "infectionControlZone": "controlled",
            "capacity": 1,
            "operationalStatus": "verified",
            "attributes": {"oxygen": True, "anaestheticMachine": True},
            "expectedVersion": 1,
            "reason": "Prepare a draft room-name change without affecting runtime.",
        }, "change room draft")
        with Session(engine) as session:
            runtime_room = session.exec(select(HospitalConfigurationRecord).where(
                HospitalConfigurationRecord.premises_ref == "premises-v27-bristol",
                HospitalConfigurationRecord.entity_type == "room",
                HospitalConfigurationRecord.entity_ref == "mri-suite-1",
            )).one()
            assert runtime_room.name == "MRI Suite 1"

        release_two = ok(client.post(
            "/api/v27/sites/referral-hospital-v27/releases/approve",
            headers=director,
            json={"reason": "Approve the reviewed room-name configuration change."},
        ), "approve second release")["release"]
        assert release_two["releaseVersion"] == 2
        with Session(engine) as session:
            runtime_room = session.exec(select(HospitalConfigurationRecord).where(
                HospitalConfigurationRecord.premises_ref == "premises-v27-bristol",
                HospitalConfigurationRecord.entity_type == "room",
                HospitalConfigurationRecord.entity_ref == "mri-suite-1",
            )).one()
            assert runtime_room.name == "MRI Suite Renamed Draft"

        rollback = ok(client.post(
            f"/api/v27/releases/{release_one['releaseRef']}/rollback",
            headers=director,
            json={"reason": "Rollback to the first approved hospital configuration after review."},
        ), "rollback first release")["release"]
        assert rollback["rollbackOfReleaseRef"] == release_one["releaseRef"]
        assert rollback["releaseVersion"] == 3
        with Session(engine) as session:
            runtime_room = session.exec(select(HospitalConfigurationRecord).where(
                HospitalConfigurationRecord.premises_ref == "premises-v27-bristol",
                HospitalConfigurationRecord.entity_type == "room",
                HospitalConfigurationRecord.entity_ref == "mri-suite-1",
            )).one()
            assert runtime_room.name == "MRI Suite 1"
            assert len(session.exec(select(ConfigurationReleaseV27).where(
                ConfigurationReleaseV27.site_ref == "referral-hospital-v27"
            )).all()) == 3
            assert len(session.exec(select(StaffAccessApprovalV27).where(
                StaffAccessApprovalV27.site_ref == "referral-hospital-v27"
            )).all()) == 3
            assert session.exec(select(StaffImportBatchV27)).all()
            assert not session.exec(select(MedicationOrder)).all()
            assert not session.exec(select(MedicationAdministration)).all()
            assert not session.exec(select(EpisodeTransitionV9)).all()
            assert not session.exec(select(EpisodeClosureV9)).all()
            chain = verify_event_chain(session)
            assert chain["valid"], chain

        print("Draft organisation, site, rooms, equipment, policies and staff remained isolated from runtime OK")
        print("Invalid staff imports and unverified clinical access rejected OK")
        print("Approved release published into existing v6 runtime and v26 context OK")
        print("Non-clinical reception role authenticated without clinical authority OK")
        print("Versioned release, pending draft and evidence-backed rollback OK")
        print("No autonomous clinical mutation and immutable evidence chain OK")
        print("--- ORGANISATION ONBOARDING V27 SMOKE TEST PASSED ---")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
