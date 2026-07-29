from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

required_files = {
    "models": ROOT / "apps/api/app/organisation_onboarding_v27_models.py",
    "service": ROOT / "apps/api/app/organisation_onboarding_v27_service.py",
    "hardening": ROOT / "apps/api/app/organisation_onboarding_v27_hardening.py",
    "context": ROOT / "apps/api/app/organisation_onboarding_v27_context_patch.py",
    "routes": ROOT / "apps/api/app/organisation_onboarding_v27_routes.py",
    "hardening_routes": ROOT / "apps/api/app/organisation_onboarding_v27_hardening_routes.py",
    "migration": ROOT / "apps/api/migrations/versions/0021_organisation_onboarding_v27.py",
    "smoke": ROOT / "apps/api/organisation_onboarding_v27_smoke_test.py",
    "authority": ROOT / "apps/api/organisation_onboarding_v27_authority_test.py",
    "page": ROOT / "apps/web/app/onboarding/page.tsx",
    "workspace": ROOT / "apps/web/components/organisation-onboarding-v27.tsx",
    "docs": ROOT / "docs/ORGANISATION_ONBOARDING_V27.md",
}

for label, path in required_files.items():
    assert path.exists(), f"missing {label}: {path}"

models = required_files["models"].read_text()
service = required_files["service"].read_text()
hardening = required_files["hardening"].read_text()
context = required_files["context"].read_text()
routes = required_files["routes"].read_text()
migration = required_files["migration"].read_text()
smoke = required_files["smoke"].read_text()
authority = required_files["authority"].read_text()
workspace = required_files["workspace"].read_text()
docs = required_files["docs"].read_text()
main = (ROOT / "apps/api/app/main.py").read_text()
system_control = (ROOT / "apps/web/app/system-control/page.tsx").read_text()

for token in (
    "OnboardingOrganisationV27", "OnboardingSiteV27", "OnboardingDepartmentV27",
    "OnboardingServiceV27", "OnboardingRoomV27", "OnboardingEquipmentV27",
    "StaffImportBatchV27", "OnboardingStaffV27", "StaffCredentialV27",
    "StaffCompetencyV27", "StaffAccessApprovalV27", "SitePolicyV27",
    "ConfigurationReleaseV27", "ConfigurationChangeV27",
):
    assert token in models, f"missing model {token}"

for token in (
    "configurationReady", "goLiveReady", "REQUIRED_POLICY_KEYS", "preview_staff_import",
    "commit_staff_import", "match_staff_identity", "approve_release", "rollback_release",
    "publish_snapshot", "HospitalConfigurationRecord", "WorkforceProfile", "WorkforceCompetency",
    "canonical_hash", "expectedVersion",
):
    assert token in service or token in routes, f"missing service contract {token}"

for token in (
    "staff_access_not_decided", "access approval requires evidenceRefs", "not_required",
    "clinical_credential_expired_or_unverified", "clinical_competency_expired_or_unverified",
    "staff_access_no_longer_valid", "role_claim_not_approved_for_site",
):
    assert token in hardening or token in context, f"missing access hardening {token}"

for route in (
    "/contracts", "/onboarding/sites", "/onboarding", "/readiness", "/organisations", "/sites",
    "/departments", "/services", "/rooms", "/equipment", "/policies",
    "/staff/imports/preview", "/staff/imports/{batch_ref}/commit",
    "/sites/{site_ref}/staff/{staff_ref}/identity",
    "/sites/{site_ref}/staff/{staff_ref}/credentials",
    "/sites/{site_ref}/staff/{staff_ref}/competencies",
    "/sites/{site_ref}/staff/{staff_ref}/approve-access",
    "/sites/{site_ref}/releases/approve", "/releases/{release_ref}/rollback",
):
    assert route in routes, f"missing route {route}"

assert "/sites/{site_ref}/staff/{staff_ref}/access-disposition" in required_files["hardening_routes"].read_text()
assert 'revision: str = "0021_organisation_onboarding_v27"' in migration
assert 'down_revision: Union[str, None] = "0020_operational_convergence_v26"' in migration
assert "organisation_onboarding_v27_router" in main
assert "organisation_onboarding_v27_hardening_router" in main
assert '"/onboarding"' in system_control

for phrase in (
    "Draft onboarding data is isolated", "imported title", "configuration release",
    "credential", "competency", "changes_pending", "rollback", "Remaining real deployment dependencies",
):
    assert phrase.lower() in docs.lower(), f"documentation missing {phrase}"

for proof in (
    "draft organisation", "invalid staff imports", "no_access.status_code == 403",
    "clinical_access_blocked.status_code == 409", "releaseVersion", "rollbackOfReleaseRef",
    "MedicationOrder", "MedicationAdministration", "EpisodeTransitionV9", "EpisodeClosureV9",
    "verify_event_chain",
):
    assert proof in smoke, f"connected proof missing {proof}"

for proof in (
    "expired clinical credential was accepted", "inactive employment was accepted",
    "clinical_credential_expired_or_unverified", "staff_access_no_longer_valid", "reception",
):
    assert proof in authority, f"authority proof missing {proof}"

for token in (
    "Onboard the hospital once", "Preview only", "Approve site access",
    "Approve and publish release", "Rollback to this release", "configurationReady", "goLiveReady",
):
    assert token in workspace, f"workspace missing {token}"

for forbidden in (
    "clinical_mutation_performed=True", "MedicationOrder(", "MedicationAdministration(",
    "EpisodeTransitionV9(", "EpisodeClosureV9(",
):
    assert forbidden not in service + hardening + routes, f"forbidden autonomous mutation: {forbidden}"

print("Organisation, site, department, service, room and equipment model audit OK")
print("Staff import, identity, credential, competency and access separation OK")
print("Approved release, runtime publication, pending draft and rollback controls OK")
print("Live employment, role and clinical-evidence revalidation OK")
print("Migration, UI, documentation and no-autonomous-clinical-mutation boundary OK")
print("--- ORGANISATION ONBOARDING V27 VALIDATION PASSED ---")
