"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Blocker = { code: string; message: string; [key: string]: unknown };
type Readiness = {
  siteRef: string;
  configurationReady: boolean;
  goLiveReady: boolean;
  activeReleaseRef?: string | null;
  configurationBlockers: Blocker[];
  accessBlockers: Blocker[];
  warnings: Blocker[];
  counts: Record<string, number>;
};
type Site = {
  siteRef: string;
  organisationRef: string;
  premisesRef: string;
  name: string;
  status: string;
  activeReleaseRef?: string | null;
};
type Staff = {
  staffRef: string;
  displayName: string;
  requestedRole: string;
  identityStatus: string;
  accessStatus: string;
  clinicalAuthorityStatus: string;
};
type Release = {
  releaseRef: string;
  releaseVersion: number;
  status: string;
  snapshotHash: string;
  effectiveAt: string;
  rollbackOfReleaseRef?: string | null;
};
type Bundle = {
  organisation?: Record<string, unknown> | null;
  site?: Site | null;
  departments?: Array<Record<string, unknown>>;
  services?: Array<Record<string, unknown>>;
  rooms?: Array<Record<string, unknown>>;
  equipment?: Array<Record<string, unknown>>;
  staff?: Staff[];
  credentials?: Array<Record<string, unknown>>;
  competencies?: Array<Record<string, unknown>>;
  policies?: Array<Record<string, unknown>>;
  releases?: Release[];
  changes?: Array<Record<string, unknown>>;
  readiness: Readiness;
};

type Preview = {
  batch: {
    batchRef: string;
    rowCount: number;
    validCount: number;
    warningCount: number;
    errorCount: number;
    findings: Blocker[];
    status: string;
  };
};

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 14 };
const field: React.CSSProperties = { width: "100%", minHeight: 40, border: "1px solid #94a3b8", borderRadius: 8, padding: "8px 10px", background: "white", color: "#0f172a" };
const button: React.CSSProperties = { minHeight: 40, border: 0, borderRadius: 9, padding: "8px 12px", background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };
const dangerButton: React.CSSProperties = { ...button, background: "#991b1b" };
const grid: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))", gap: 9 };

function value(record: Record<string, unknown> | undefined, key: string): string {
  const raw = record?.[key];
  return raw === null || raw === undefined ? "" : String(raw);
}

export function OrganisationOnboardingV27() {
  const [siteRef, setSiteRef] = useState("bvs-bristol");
  const [sites, setSites] = useState<Site[]>([]);
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<Preview["batch"] | null>(null);

  const [orgForm, setOrgForm] = useState({
    organisationRef: "", legalName: "", tradingName: "", companyNumber: "", postcode: "",
    dataControllerName: "", dataControllerEmail: "", accountableExecutiveSubject: "",
  });
  const [siteForm, setSiteForm] = useState({
    siteRef: "", premisesRef: "", name: "", postcode: "", accountableDirectorSubject: "", clinicalGovernanceSubject: "",
  });
  const [departmentForm, setDepartmentForm] = useState({ departmentRef: "", name: "", accountableSubject: "" });
  const [serviceForm, setServiceForm] = useState({ serviceRef: "", departmentRef: "", name: "", minimumStaffing: "clinician:1,nurse:1", requiredEquipmentRefs: "" });
  const [roomForm, setRoomForm] = useState({ roomRef: "", departmentRef: "", name: "", roomType: "clinical_room", serviceRefs: "" });
  const [equipmentForm, setEquipmentForm] = useState({ equipmentRef: "", name: "", equipmentType: "equipment", roomRef: "", serviceRefs: "", maintenanceDueAt: "" });
  const [policyForm, setPolicyForm] = useState({ policyKey: "", title: "", policyVersion: "1.0", ownerSubject: "", evidenceRef: "", rules: "{}" });
  const [staffRows, setStaffRows] = useState("[]");
  const [staffAction, setStaffAction] = useState({ staffRef: "", authSubject: "", credentialNumber: "", competencyRef: "", evidenceRef: "" });
  const [releaseReason, setReleaseReason] = useState("Approved after hospital configuration review.");

  async function refreshSites() {
    const result = await apiGet<{ sites: Site[] }>("/api/v27/onboarding/sites");
    setSites(result.sites);
    if (result.sites.length && !siteRef) setSiteRef(result.sites[0].siteRef);
  }

  async function load(ref = siteRef) {
    if (!ref.trim()) return;
    const result = await apiGet<Bundle>(`/api/v27/onboarding?siteRef=${encodeURIComponent(ref.trim())}`);
    setBundle(result);
    setSiteRef(ref.trim());
    if (result.organisation) {
      setOrgForm(current => ({
        ...current,
        organisationRef: value(result.organisation || undefined, "organisationRef"),
        legalName: value(result.organisation || undefined, "legalName"),
        tradingName: value(result.organisation || undefined, "tradingName"),
        companyNumber: value(result.organisation || undefined, "companyNumber"),
        dataControllerName: value(result.organisation || undefined, "dataControllerName"),
        dataControllerEmail: value(result.organisation || undefined, "dataControllerEmail"),
        accountableExecutiveSubject: value(result.organisation || undefined, "accountableExecutiveSubject"),
      }));
    }
    if (result.site) {
      setSiteForm(current => ({
        ...current,
        siteRef: result.site?.siteRef || ref,
        premisesRef: result.site?.premisesRef || "",
        name: result.site?.name || "",
      }));
    }
  }

  async function run(label: string, work: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      setNotice(label);
      await refreshSites();
      if (siteRef) await load(siteRef);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void refreshSites().catch(caught => setError(caught instanceof Error ? caught.message : "Unable to load onboarding sites"));
  }, []);

  useEffect(() => {
    if (sites.some(site => site.siteRef === siteRef)) void load(siteRef).catch(caught => setError(caught instanceof Error ? caught.message : "Unable to load onboarding workspace"));
  }, [sites.length]);

  const readiness = bundle?.readiness;
  const counts = readiness?.counts || {};
  const requiredPolicies = useMemo(() => [
    "fatigue_and_safe_staffing", "patient_safety_escalation", "service_restriction",
    "safeguarding", "data_retention", "downtime_and_recovery",
  ], []);

  async function saveOrganisationAndSite(event: FormEvent) {
    event.preventDefault();
    const targetSiteRef = siteForm.siteRef.trim();
    await run("Organisation and hospital site saved as draft.", async () => {
      await apiPost("/api/v27/organisations", { payload: {
        organisationRef: orgForm.organisationRef.trim(),
        legalName: orgForm.legalName.trim(),
        tradingName: orgForm.tradingName.trim() || null,
        companyNumber: orgForm.companyNumber.trim() || null,
        countryCode: "GB",
        registeredAddress: { postcode: orgForm.postcode.trim() },
        dataControllerName: orgForm.dataControllerName.trim(),
        dataControllerEmail: orgForm.dataControllerEmail.trim(),
        accountableExecutiveSubject: orgForm.accountableExecutiveSubject.trim(),
        accountableExecutiveName: orgForm.accountableExecutiveSubject.trim(),
        reason: "Organisation onboarding form updated.",
      }});
      await apiPost("/api/v27/sites", { payload: {
        siteRef: targetSiteRef,
        organisationRef: orgForm.organisationRef.trim(),
        premisesRef: siteForm.premisesRef.trim(),
        name: siteForm.name.trim(),
        siteType: "referral_hospital",
        timezone: "Europe/London",
        address: { postcode: siteForm.postcode.trim() },
        accountableDirectorSubject: siteForm.accountableDirectorSubject.trim(),
        accountableDirectorName: siteForm.accountableDirectorSubject.trim(),
        clinicalGovernanceSubject: siteForm.clinicalGovernanceSubject.trim(),
        clinicalGovernanceName: siteForm.clinicalGovernanceSubject.trim(),
        reason: "Hospital site onboarding form updated.",
      }});
      setSiteRef(targetSiteRef);
    });
  }

  async function addDepartment(event: FormEvent) {
    event.preventDefault();
    await run("Department saved.", async () => {
      await apiPost("/api/v27/departments", { payload: {
        siteRef, departmentRef: departmentForm.departmentRef.trim(), name: departmentForm.name.trim(),
        departmentType: "clinical", accountableRole: "department_lead",
        accountableSubject: departmentForm.accountableSubject.trim() || null, status: "verified",
        reason: "Department configured in onboarding workspace.",
      }});
    });
  }

  async function addService(event: FormEvent) {
    event.preventDefault();
    const minimumStaffing = serviceForm.minimumStaffing.split(",").map(item => item.trim()).filter(Boolean).map(item => {
      const [role, count] = item.split(":");
      return { role: role.trim(), minimum: Number(count || 1) };
    });
    await run("Service saved.", async () => {
      await apiPost("/api/v27/services", { payload: {
        siteRef, serviceRef: serviceForm.serviceRef.trim(), departmentRef: serviceForm.departmentRef.trim(),
        name: serviceForm.name.trim(), serviceType: "clinical", clinicalService: true,
        operationalStatus: "verified", minimumStaffing,
        requiredEquipmentRefs: serviceForm.requiredEquipmentRefs.split(",").map(v => v.trim()).filter(Boolean),
        escalationRole: "clinical_director", reason: "Hospital service configured.",
      }});
    });
  }

  async function addRoom(event: FormEvent) {
    event.preventDefault();
    await run("Room saved.", async () => {
      await apiPost("/api/v27/rooms", { payload: {
        siteRef, roomRef: roomForm.roomRef.trim(), departmentRef: roomForm.departmentRef.trim(),
        name: roomForm.name.trim(), roomType: roomForm.roomType.trim(),
        serviceRefs: roomForm.serviceRefs.split(",").map(v => v.trim()).filter(Boolean),
        capacity: 1, operationalStatus: "verified", reason: "Hospital room configured.",
      }});
    });
  }

  async function addEquipment(event: FormEvent) {
    event.preventDefault();
    await run("Equipment saved.", async () => {
      await apiPost("/api/v27/equipment", { payload: {
        siteRef, equipmentRef: equipmentForm.equipmentRef.trim(), name: equipmentForm.name.trim(),
        equipmentType: equipmentForm.equipmentType.trim(), roomRef: equipmentForm.roomRef.trim() || null,
        serviceRefs: equipmentForm.serviceRefs.split(",").map(v => v.trim()).filter(Boolean),
        maintenanceStatus: "verified", maintenanceDueAt: equipmentForm.maintenanceDueAt || null,
        operationalStatus: "verified", reason: "Hospital equipment and maintenance status configured.",
      }});
    });
  }

  async function addPolicy(event: FormEvent) {
    event.preventDefault();
    await run("Policy saved.", async () => {
      const rules = JSON.parse(policyForm.rules || "{}");
      await apiPost("/api/v27/policies", { payload: {
        siteRef, policyKey: policyForm.policyKey.trim(), title: policyForm.title.trim(),
        policyVersion: policyForm.policyVersion.trim(), status: "approved", rules,
        ownerRole: "governance_lead", ownerSubject: policyForm.ownerSubject.trim() || null,
        evidenceRefs: [policyForm.evidenceRef.trim()].filter(Boolean),
        reason: "Hospital-specific policy approved with evidence.",
      }});
    });
  }

  async function previewStaff(event: FormEvent) {
    event.preventDefault();
    await run("Staff import preview completed.", async () => {
      const rows = JSON.parse(staffRows);
      const result = await apiPost<Preview>("/api/v27/staff/imports/preview", {
        siteRef, sourceType: "json", sourceRef: "onboarding-workspace", rows,
        reason: "Preview staff import before any onboarding record or access change.",
      });
      setPreview(result.batch);
    });
  }

  async function commitStaff() {
    if (!preview) return;
    await run("Validated staff import committed as onboarding data only.", async () => {
      await apiPost(`/api/v27/staff/imports/${encodeURIComponent(preview.batchRef)}/commit`, {
        reason: "Commit the validated staff directory import without granting access.",
      });
      setPreview(null);
    });
  }

  async function verifyIdentity() {
    await run("Staff identity matched.", async () => {
      await apiPost(`/api/v27/sites/${encodeURIComponent(siteRef)}/staff/${encodeURIComponent(staffAction.staffRef)}/identity`, {
        authSubject: staffAction.authSubject.trim(), reason: "Independently match staff and authenticated identity.",
      });
    });
  }

  async function verifyCredential() {
    await run("Professional credential verified.", async () => {
      await apiPost(`/api/v27/sites/${encodeURIComponent(siteRef)}/staff/${encodeURIComponent(staffAction.staffRef)}/credentials`, { payload: {
        credentialType: "professional_registration", issuingBody: "RCVS",
        credentialNumber: staffAction.credentialNumber.trim(), verificationStatus: "verified",
        evidenceRefs: [staffAction.evidenceRef.trim()].filter(Boolean),
        reason: "Verify current professional-registration evidence.",
      }});
    });
  }

  async function verifyCompetency() {
    await run("Competency verified.", async () => {
      await apiPost(`/api/v27/sites/${encodeURIComponent(siteRef)}/staff/${encodeURIComponent(staffAction.staffRef)}/competencies`, { payload: {
        competencyRef: staffAction.competencyRef.trim(), scopeRef: "hospital", level: "independent",
        verificationStatus: "verified", evidenceSummary: "Reviewed in onboarding workspace.",
        evidenceRefs: [staffAction.evidenceRef.trim()].filter(Boolean),
        reason: "Verify competency evidence for the requested hospital role.",
      }});
    });
  }

  async function approveAccess() {
    await run("Hospital-site access approved.", async () => {
      await apiPost(`/api/v27/sites/${encodeURIComponent(siteRef)}/staff/${encodeURIComponent(staffAction.staffRef)}/approve-access`, {
        reason: "Approve the independently verified role for this hospital site.",
        evidenceRefs: [staffAction.evidenceRef.trim()].filter(Boolean),
      });
    });
  }

  async function approveRelease() {
    await run("Configuration release approved and published.", async () => {
      await apiPost(`/api/v27/sites/${encodeURIComponent(siteRef)}/releases/approve`, { reason: releaseReason.trim() });
    });
  }

  async function rollbackRelease(releaseRef: string) {
    await run("Rollback release created and published.", async () => {
      await apiPost(`/api/v27/releases/${encodeURIComponent(releaseRef)}/rollback`, {
        reason: `Rollback approved after reviewing release ${releaseRef}.`,
      });
    });
  }

  return (
    <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 10, fontFamily: "Inter,system-ui,sans-serif" }}>
      <header style={{ ...panel, background: "#071019", color: "white", padding: 18 }}>
        <span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>LUCYWORKS OS · V27</span>
        <h1 style={{ margin: "7px 0", fontSize: "clamp(34px,7vw,64px)", lineHeight: .94 }}>Onboard the hospital once</h1>
        <p style={{ color: "#cbd5e1", maxWidth: 920, marginBottom: 12 }}>Draft configuration is isolated. Only an approved release reaches live hospital context, runtime configuration and workforce records. Staff access is a separate evidence-backed decision.</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <input list="v27-sites" value={siteRef} onChange={event => setSiteRef(event.target.value)} placeholder="hospital site reference" style={{ ...field, width: 280 }} />
          <datalist id="v27-sites">{sites.map(site => <option key={site.siteRef} value={site.siteRef}>{site.name}</option>)}</datalist>
          <button type="button" disabled={busy || !siteRef.trim()} onClick={() => void load()} style={button}>Load hospital</button>
        </div>
      </header>

      {(error || notice) && <div role="status" style={{ marginTop: 8, padding: 11, borderRadius: 10, background: error ? "#fee2e2" : "#dcfce7", color: error ? "#7f1d1d" : "#14532d", fontWeight: 800 }}>{error || notice}</div>}

      <section style={{ ...grid, marginTop: 9 }}>
        <article style={panel}><small>CONFIGURATION RELEASE</small><strong style={{ display: "block", fontSize: 28 }}>{readiness?.configurationReady ? "Ready" : "Blocked"}</strong><span>{readiness?.configurationBlockers.length || 0} blockers</span></article>
        <article style={panel}><small>OPERATIONAL ACCESS</small><strong style={{ display: "block", fontSize: 28 }}>{readiness?.goLiveReady ? "Ready" : "Blocked"}</strong><span>{readiness?.accessBlockers.length || 0} access blockers</span></article>
        <article style={panel}><small>ACTIVE RELEASE</small><strong style={{ display: "block", fontSize: 20, wordBreak: "break-all" }}>{readiness?.activeReleaseRef || "None"}</strong></article>
        <article style={panel}><small>CONFIGURED</small><strong style={{ display: "block", fontSize: 20 }}>{counts.services || 0} services · {counts.rooms || 0} rooms</strong><span>{counts.activeStaff || 0} active staff · {counts.accessApprovals || 0} access approvals</span></article>
      </section>

      {(readiness?.configurationBlockers.length || readiness?.accessBlockers.length || readiness?.warnings.length) ? <section style={{ ...panel, marginTop: 9 }}>
        <h2 style={{ marginTop: 0 }}>What still blocks release or go-live</h2>
        <div style={grid}>
          {[...(readiness?.configurationBlockers || []).map(item => ({ ...item, group: "Configuration" })), ...(readiness?.accessBlockers || []).map(item => ({ ...item, group: "Access" })), ...(readiness?.warnings || []).map(item => ({ ...item, group: "Warning" }))].map((item, index) => (
            <div key={`${item.code}-${index}`} style={{ borderLeft: `5px solid ${item.group === "Warning" ? "#ca8a04" : "#b91c1c"}`, padding: 9, background: "#f8fafc", borderRadius: 8 }}>
              <strong>{item.group}: {item.code}</strong><div>{item.message}</div>
            </div>
          ))}
        </div>
      </section> : null}

      <details open style={{ ...panel, marginTop: 9 }}>
        <summary style={{ cursor: "pointer", fontSize: 22, fontWeight: 900 }}>1. Legal organisation and hospital site</summary>
        <form onSubmit={saveOrganisationAndSite} style={{ ...grid, marginTop: 12 }}>
          <input required value={orgForm.organisationRef} onChange={e => setOrgForm({ ...orgForm, organisationRef: e.target.value })} placeholder="organisation reference" style={field} />
          <input required value={orgForm.legalName} onChange={e => setOrgForm({ ...orgForm, legalName: e.target.value })} placeholder="legal organisation name" style={field} />
          <input value={orgForm.tradingName} onChange={e => setOrgForm({ ...orgForm, tradingName: e.target.value })} placeholder="trading name" style={field} />
          <input value={orgForm.companyNumber} onChange={e => setOrgForm({ ...orgForm, companyNumber: e.target.value })} placeholder="company number" style={field} />
          <input required value={orgForm.postcode} onChange={e => setOrgForm({ ...orgForm, postcode: e.target.value })} placeholder="registered-address postcode" style={field} />
          <input required value={orgForm.dataControllerName} onChange={e => setOrgForm({ ...orgForm, dataControllerName: e.target.value })} placeholder="data controller name" style={field} />
          <input required type="email" value={orgForm.dataControllerEmail} onChange={e => setOrgForm({ ...orgForm, dataControllerEmail: e.target.value })} placeholder="data controller email" style={field} />
          <input required value={orgForm.accountableExecutiveSubject} onChange={e => setOrgForm({ ...orgForm, accountableExecutiveSubject: e.target.value })} placeholder="accountable executive subject" style={field} />
          <input required value={siteForm.siteRef} onChange={e => setSiteForm({ ...siteForm, siteRef: e.target.value })} placeholder="site reference" style={field} />
          <input required value={siteForm.premisesRef} onChange={e => setSiteForm({ ...siteForm, premisesRef: e.target.value })} placeholder="premises reference" style={field} />
          <input required value={siteForm.name} onChange={e => setSiteForm({ ...siteForm, name: e.target.value })} placeholder="hospital name" style={field} />
          <input required value={siteForm.postcode} onChange={e => setSiteForm({ ...siteForm, postcode: e.target.value })} placeholder="hospital postcode" style={field} />
          <input required value={siteForm.accountableDirectorSubject} onChange={e => setSiteForm({ ...siteForm, accountableDirectorSubject: e.target.value })} placeholder="hospital director subject" style={field} />
          <input required value={siteForm.clinicalGovernanceSubject} onChange={e => setSiteForm({ ...siteForm, clinicalGovernanceSubject: e.target.value })} placeholder="clinical governance subject" style={field} />
          <button disabled={busy} style={button}>Save legal and site draft</button>
        </form>
      </details>

      <details style={{ ...panel, marginTop: 9 }}>
        <summary style={{ cursor: "pointer", fontSize: 22, fontWeight: 900 }}>2. Departments, services, rooms and equipment</summary>
        <div style={{ ...grid, marginTop: 12 }}>
          <form onSubmit={addDepartment} style={{ display: "grid", gap: 7 }}><h3>Department</h3><input required value={departmentForm.departmentRef} onChange={e => setDepartmentForm({ ...departmentForm, departmentRef: e.target.value })} placeholder="department ref" style={field} /><input required value={departmentForm.name} onChange={e => setDepartmentForm({ ...departmentForm, name: e.target.value })} placeholder="name" style={field} /><input value={departmentForm.accountableSubject} onChange={e => setDepartmentForm({ ...departmentForm, accountableSubject: e.target.value })} placeholder="accountable subject" style={field} /><button disabled={busy} style={button}>Save department</button></form>
          <form onSubmit={addService} style={{ display: "grid", gap: 7 }}><h3>Service</h3><input required value={serviceForm.serviceRef} onChange={e => setServiceForm({ ...serviceForm, serviceRef: e.target.value })} placeholder="service ref" style={field} /><input required value={serviceForm.departmentRef} onChange={e => setServiceForm({ ...serviceForm, departmentRef: e.target.value })} placeholder="department ref" style={field} /><input required value={serviceForm.name} onChange={e => setServiceForm({ ...serviceForm, name: e.target.value })} placeholder="name" style={field} /><input value={serviceForm.minimumStaffing} onChange={e => setServiceForm({ ...serviceForm, minimumStaffing: e.target.value })} placeholder="clinician:1,nurse:1" style={field} /><input value={serviceForm.requiredEquipmentRefs} onChange={e => setServiceForm({ ...serviceForm, requiredEquipmentRefs: e.target.value })} placeholder="equipment refs, comma separated" style={field} /><button disabled={busy} style={button}>Save service</button></form>
          <form onSubmit={addRoom} style={{ display: "grid", gap: 7 }}><h3>Room</h3><input required value={roomForm.roomRef} onChange={e => setRoomForm({ ...roomForm, roomRef: e.target.value })} placeholder="room ref" style={field} /><input required value={roomForm.departmentRef} onChange={e => setRoomForm({ ...roomForm, departmentRef: e.target.value })} placeholder="department ref" style={field} /><input required value={roomForm.name} onChange={e => setRoomForm({ ...roomForm, name: e.target.value })} placeholder="name" style={field} /><input value={roomForm.roomType} onChange={e => setRoomForm({ ...roomForm, roomType: e.target.value })} placeholder="room type" style={field} /><input value={roomForm.serviceRefs} onChange={e => setRoomForm({ ...roomForm, serviceRefs: e.target.value })} placeholder="service refs" style={field} /><button disabled={busy} style={button}>Save room</button></form>
          <form onSubmit={addEquipment} style={{ display: "grid", gap: 7 }}><h3>Equipment</h3><input required value={equipmentForm.equipmentRef} onChange={e => setEquipmentForm({ ...equipmentForm, equipmentRef: e.target.value })} placeholder="equipment ref" style={field} /><input required value={equipmentForm.name} onChange={e => setEquipmentForm({ ...equipmentForm, name: e.target.value })} placeholder="name" style={field} /><input value={equipmentForm.equipmentType} onChange={e => setEquipmentForm({ ...equipmentForm, equipmentType: e.target.value })} placeholder="type" style={field} /><input value={equipmentForm.roomRef} onChange={e => setEquipmentForm({ ...equipmentForm, roomRef: e.target.value })} placeholder="room ref" style={field} /><input value={equipmentForm.serviceRefs} onChange={e => setEquipmentForm({ ...equipmentForm, serviceRefs: e.target.value })} placeholder="service refs" style={field} /><input type="date" value={equipmentForm.maintenanceDueAt} onChange={e => setEquipmentForm({ ...equipmentForm, maintenanceDueAt: e.target.value })} style={field} /><button disabled={busy} style={button}>Save equipment</button></form>
        </div>
      </details>

      <details style={{ ...panel, marginTop: 9 }}>
        <summary style={{ cursor: "pointer", fontSize: 22, fontWeight: 900 }}>3. Workforce import and access evidence</summary>
        <div style={{ ...grid, marginTop: 12 }}>
          <form onSubmit={previewStaff} style={{ display: "grid", gap: 8 }}>
            <h3>Import preview</h3>
            <textarea value={staffRows} onChange={e => setStaffRows(e.target.value)} rows={12} style={{ ...field, fontFamily: "ui-monospace,monospace" }} aria-label="Staff import JSON" />
            <button disabled={busy} style={button}>Preview only</button>
            {preview && <div><strong>{preview.validCount}/{preview.rowCount} valid</strong><div>{preview.warningCount} warnings · {preview.errorCount} errors</div><button type="button" disabled={busy || preview.errorCount > 0} onClick={() => void commitStaff()} style={{ ...button, marginTop: 8 }}>Commit onboarding records</button></div>}
          </form>
          <div style={{ display: "grid", gap: 8 }}>
            <h3>Identity, professional evidence and access</h3>
            <select value={staffAction.staffRef} onChange={e => setStaffAction({ ...staffAction, staffRef: e.target.value })} style={field}><option value="">Select staff member</option>{(bundle?.staff || []).map(person => <option key={person.staffRef} value={person.staffRef}>{person.displayName} · {person.requestedRole}</option>)}</select>
            <input value={staffAction.authSubject} onChange={e => setStaffAction({ ...staffAction, authSubject: e.target.value })} placeholder="verified auth subject" style={field} />
            <input value={staffAction.credentialNumber} onChange={e => setStaffAction({ ...staffAction, credentialNumber: e.target.value })} placeholder="professional registration number" style={field} />
            <input value={staffAction.competencyRef} onChange={e => setStaffAction({ ...staffAction, competencyRef: e.target.value })} placeholder="competency reference" style={field} />
            <input value={staffAction.evidenceRef} onChange={e => setStaffAction({ ...staffAction, evidenceRef: e.target.value })} placeholder="evidence reference" style={field} />
            <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}><button type="button" disabled={busy || !staffAction.staffRef || !staffAction.authSubject} onClick={() => void verifyIdentity()} style={button}>Match identity</button><button type="button" disabled={busy || !staffAction.staffRef || !staffAction.credentialNumber || !staffAction.evidenceRef} onClick={() => void verifyCredential()} style={button}>Verify credential</button><button type="button" disabled={busy || !staffAction.staffRef || !staffAction.competencyRef || !staffAction.evidenceRef} onClick={() => void verifyCompetency()} style={button}>Verify competency</button><button type="button" disabled={busy || !staffAction.staffRef || !staffAction.evidenceRef || !readiness?.activeReleaseRef} onClick={() => void approveAccess()} style={dangerButton}>Approve site access</button></div>
            <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr><th align="left">Staff</th><th align="left">Role</th><th align="left">Identity</th><th align="left">Access</th></tr></thead><tbody>{(bundle?.staff || []).map(person => <tr key={person.staffRef}><td>{person.displayName}</td><td>{person.requestedRole}</td><td>{person.identityStatus}</td><td>{person.accessStatus}</td></tr>)}</tbody></table></div>
          </div>
        </div>
      </details>

      <details style={{ ...panel, marginTop: 9 }}>
        <summary style={{ cursor: "pointer", fontSize: 22, fontWeight: 900 }}>4. Hospital-specific policies</summary>
        <p>Required: {requiredPolicies.join(", ")}. Approval requires a real evidence reference; this screen does not invent policy content.</p>
        <form onSubmit={addPolicy} style={grid}><select required value={policyForm.policyKey} onChange={e => setPolicyForm({ ...policyForm, policyKey: e.target.value, title: e.target.value.replaceAll("_", " ") })} style={field}><option value="">Select required policy</option>{requiredPolicies.map(key => <option key={key} value={key}>{key}</option>)}</select><input required value={policyForm.title} onChange={e => setPolicyForm({ ...policyForm, title: e.target.value })} placeholder="title" style={field} /><input required value={policyForm.policyVersion} onChange={e => setPolicyForm({ ...policyForm, policyVersion: e.target.value })} placeholder="version" style={field} /><input value={policyForm.ownerSubject} onChange={e => setPolicyForm({ ...policyForm, ownerSubject: e.target.value })} placeholder="owner subject" style={field} /><input required value={policyForm.evidenceRef} onChange={e => setPolicyForm({ ...policyForm, evidenceRef: e.target.value })} placeholder="approved policy evidence ref" style={field} /><textarea value={policyForm.rules} onChange={e => setPolicyForm({ ...policyForm, rules: e.target.value })} rows={4} style={{ ...field, fontFamily: "ui-monospace,monospace" }} /><button disabled={busy} style={button}>Save approved policy</button></form>
      </details>

      <details open style={{ ...panel, marginTop: 9 }}>
        <summary style={{ cursor: "pointer", fontSize: 22, fontWeight: 900 }}>5. Approve, publish or rollback a configuration release</summary>
        <p>Approval publishes the exact snapshot into the existing runtime configuration and workforce tables. Later drafts remain isolated until another release is approved.</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}><input value={releaseReason} onChange={e => setReleaseReason(e.target.value)} style={{ ...field, flex: "1 1 360px" }} /><button type="button" disabled={busy || !readiness?.configurationReady} onClick={() => void approveRelease()} style={dangerButton}>Approve and publish release</button></div>
        <div style={{ ...grid, marginTop: 12 }}>{(bundle?.releases || []).map(release => <article key={release.releaseRef} style={{ padding: 10, border: "1px solid #e2e8f0", borderRadius: 9 }}><strong>Release {release.releaseVersion} · {release.status}</strong><div style={{ fontSize: 12, wordBreak: "break-all" }}>{release.releaseRef}</div><div style={{ fontSize: 12 }}>Hash {release.snapshotHash.slice(0, 16)}…</div>{release.status !== "active" && <button type="button" disabled={busy} onClick={() => void rollbackRelease(release.releaseRef)} style={{ ...dangerButton, marginTop: 8 }}>Rollback to this release</button>}</article>)}</div>
      </details>
    </main>
  );
}
