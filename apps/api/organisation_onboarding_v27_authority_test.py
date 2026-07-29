import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_v27_authority_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "V27_CONFIGURATION_REQUIRED": "true",
})

from fastapi import HTTPException
from sqlmodel import SQLModel, Session, select

from app import auth_roles_v27_patch as _auth_roles_v27_patch  # noqa: F401
from app.auth import AuthContext
from app.database import engine
from app.operational_context_v26_models import SiteV26
from app.organisation_onboarding_v27_models import (
    OnboardingSiteV27,
    OnboardingStaffV27,
    StaffAccessApprovalV27,
    StaffCompetencyV27,
    StaffCredentialV27,
)
from app.organisation_onboarding_v27_context_patch import governed_memberships_for

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

clinician_auth = AuthContext(
    subject="authority-clinician-v27",
    actor_id="authority-clinician-v27",
    actor_name="Authority Clinician",
    role="clinician",
    auth_source="test",
    verified=True,
)
reception_auth = AuthContext(
    subject="authority-reception-v27",
    actor_id="authority-reception-v27",
    actor_name="Authority Reception",
    role="reception",
    auth_source="test",
    verified=True,
)

try:
    with Session(engine) as session:
        session.add(OnboardingSiteV27(
            site_ref="authority-site-v27",
            organisation_ref="authority-org-v27",
            premises_ref="authority-premises-v27",
            name="Authority Hospital",
            status="approved",
            active_release_ref="release-authority-v27",
            updated_by_subject="test",
            updated_by_name="Test",
            updated_by_role="admin",
        ))
        session.add(SiteV26(
            site_ref="authority-site-v27",
            organisation_ref="authority-org-v27",
            premises_ref="authority-premises-v27",
            name="Authority Hospital",
            status="active",
            configuration_state="approved_v27",
        ))
        session.add_all([
            OnboardingStaffV27(
                organisation_ref="authority-org-v27",
                site_ref="authority-site-v27",
                premises_ref="authority-premises-v27",
                staff_ref="clinician-staff-v27",
                display_name="Authority Clinician",
                auth_subject=clinician_auth.subject,
                identity_status="verified",
                employment_status="active",
                department_ref="clinical",
                requested_role="clinician",
                primary_role_ref="veterinary_surgeon",
                access_status="approved",
                clinical_authority_status="verified",
                updated_by_subject="test",
            ),
            OnboardingStaffV27(
                organisation_ref="authority-org-v27",
                site_ref="authority-site-v27",
                premises_ref="authority-premises-v27",
                staff_ref="reception-staff-v27",
                display_name="Authority Reception",
                auth_subject=reception_auth.subject,
                identity_status="verified",
                employment_status="active",
                department_ref="reception",
                requested_role="reception",
                primary_role_ref="reception",
                access_status="approved",
                clinical_authority_status="not_applicable",
                updated_by_subject="test",
            ),
        ])
        session.add_all([
            StaffAccessApprovalV27(
                approval_ref="approval-clinician-v27",
                organisation_ref="authority-org-v27",
                site_ref="authority-site-v27",
                premises_ref="authority-premises-v27",
                staff_ref="clinician-staff-v27",
                auth_subject=clinician_auth.subject,
                approved_role="clinician",
                clinical_authority_status="verified",
                reason="test",
                evidence_refs=["access-review"],
                approved_by_subject="test",
                approved_by_name="Test",
                approved_by_role="admin",
            ),
            StaffAccessApprovalV27(
                approval_ref="approval-reception-v27",
                organisation_ref="authority-org-v27",
                site_ref="authority-site-v27",
                premises_ref="authority-premises-v27",
                staff_ref="reception-staff-v27",
                auth_subject=reception_auth.subject,
                approved_role="reception",
                clinical_authority_status="not_applicable",
                reason="test",
                evidence_refs=["access-review"],
                approved_by_subject="test",
                approved_by_name="Test",
                approved_by_role="admin",
            ),
            StaffCredentialV27(
                credential_ref="expired-credential-v27",
                organisation_ref="authority-org-v27",
                site_ref="authority-site-v27",
                premises_ref="authority-premises-v27",
                staff_ref="clinician-staff-v27",
                credential_type="professional_registration",
                issuing_body="RCVS",
                credential_number="AUTH-V27",
                valid_until=date.today() - timedelta(days=1),
                verification_status="verified",
                evidence_refs=["register-check"],
            ),
            StaffCompetencyV27(
                competency_record_ref="valid-competency-v27",
                organisation_ref="authority-org-v27",
                site_ref="authority-site-v27",
                premises_ref="authority-premises-v27",
                staff_ref="clinician-staff-v27",
                competency_ref="clinical-practice",
                scope_ref="hospital",
                level="independent",
                verification_status="verified",
                evidence_refs=["competency-review"],
                valid_until=date.today() + timedelta(days=30),
            ),
        ])
        session.commit()

        try:
            governed_memberships_for(session, clinician_auth)
            raise AssertionError("expired clinical credential was accepted")
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail["code"] == "clinical_credential_expired_or_unverified"

        credential = session.exec(select(StaffCredentialV27).where(
            StaffCredentialV27.credential_ref == "expired-credential-v27"
        )).one()
        credential.valid_until = date.today() + timedelta(days=30)
        session.add(credential)
        session.commit()
        clinician_memberships = governed_memberships_for(session, clinician_auth)
        assert clinician_memberships[0].role == "clinician"

        reception_memberships = governed_memberships_for(session, reception_auth)
        assert reception_memberships[0].role == "reception"

        clinician = session.exec(select(OnboardingStaffV27).where(
            OnboardingStaffV27.staff_ref == "clinician-staff-v27"
        )).one()
        clinician.employment_status = "inactive"
        session.add(clinician)
        session.commit()
        try:
            governed_memberships_for(session, clinician_auth)
            raise AssertionError("inactive employment was accepted")
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail["code"] == "staff_access_no_longer_valid"

    print("Expired clinical credential blocks hospital context OK")
    print("Current credential and competency permit approved clinical context OK")
    print("Approved non-clinical role works without clinical authority OK")
    print("Inactive employment immediately blocks context OK")
    print("--- ORGANISATION ONBOARDING V27 AUTHORITY TEST PASSED ---")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
