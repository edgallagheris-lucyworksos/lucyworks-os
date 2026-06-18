"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type StaffOption = { id: number; name: string; role: string; area: string; active?: boolean };
type ResourceOption = { id: string; name: string; type: string; active?: boolean };

export function AssignmentDirectoryManager() {
  const [staff, setStaff] = useState<StaffOption[]>([]);
  const [resources, setResources] = useState<ResourceOption[]>([]);
  const [status, setStatus] = useState("ready");
  const [staffForm, setStaffForm] = useState({ name: "", role: "", area: "" });
  const [resourceForm, setResourceForm] = useState({ id: "", name: "", type: "" });

  async function refresh() {
    try {
      const [staffResponse, resourceResponse] = await Promise.all([
        fetch(`${API_BASE}/api/day-control/staff-options`),
        fetch(`${API_BASE}/api/day-control/resource-options`),
      ]);
      const staffData = await staffResponse.json();
      const resourceData = await resourceResponse.json();
      setStaff(Array.isArray(staffData.staff) ? staffData.staff : []);
      setResources(Array.isArray(resourceData.resources) ? resourceData.resources : []);
      setStatus("ready");
    } catch {
      setStatus("directory offline");
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function createStaff() {
    if (!staffForm.name || !staffForm.role || !staffForm.area) return setStatus("complete staff fields");
    try {
      await fetch(`${API_BASE}/api/day-control/staff-options`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...staffForm, active: true }) });
      setStaffForm({ name: "", role: "", area: "" });
      setStatus("staff option saved");
      await refresh();
    } catch {
      setStatus("staff save failed");
    }
  }

  async function createResource() {
    if (!resourceForm.id || !resourceForm.name || !resourceForm.type) return setStatus("complete resource fields");
    try {
      await fetch(`${API_BASE}/api/day-control/resource-options`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...resourceForm, active: true }) });
      setResourceForm({ id: "", name: "", type: "" });
      setStatus("resource option saved");
      await refresh();
    } catch {
      setStatus("resource save failed");
    }
  }

  async function deactivateStaff(item: StaffOption) {
    await fetch(`${API_BASE}/api/day-control/staff-options/${item.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: item.name, role: item.role, area: item.area, active: false }) });
    await refresh();
  }

  async function deactivateResource(item: ResourceOption) {
    await fetch(`${API_BASE}/api/day-control/resource-options/${item.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: item.id, name: item.name, type: item.type, active: false }) });
    await refresh();
  }

  return <section className="adm"><style>{css}</style><header><span>Assignment directory</span><h2>Staff and resource options</h2><p>{status}</p></header><div className="forms"><article><b>Add staff option</b><input value={staffForm.name} onChange={(e) => setStaffForm({ ...staffForm, name: e.target.value })} placeholder="Name" /><input value={staffForm.role} onChange={(e) => setStaffForm({ ...staffForm, role: e.target.value })} placeholder="Role" /><input value={staffForm.area} onChange={(e) => setStaffForm({ ...staffForm, area: e.target.value })} placeholder="Area" /><button onClick={createStaff}>Add staff</button></article><article><b>Add resource option</b><input value={resourceForm.id} onChange={(e) => setResourceForm({ ...resourceForm, id: e.target.value })} placeholder="Resource ID" /><input value={resourceForm.name} onChange={(e) => setResourceForm({ ...resourceForm, name: e.target.value })} placeholder="Name" /><input value={resourceForm.type} onChange={(e) => setResourceForm({ ...resourceForm, type: e.target.value })} placeholder="Type" /><button onClick={createResource}>Add resource</button></article></div><div className="lists"><article><b>Staff</b>{staff.map((item) => <section key={item.id}><span>{item.name}</span><small>{item.role} · {item.area}</small><button onClick={() => deactivateStaff(item)}>Deactivate</button></section>)}</article><article><b>Resources</b>{resources.map((item) => <section key={item.id}><span>{item.name}</span><small>{item.id} · {item.type}</small><button onClick={() => deactivateResource(item)}>Deactivate</button></section>)}</article></div></section>;
}

const css = `.adm{display:grid;gap:12px;border:1px solid #28466e;border-radius:18px;background:#07111f;color:#e6edf7;padding:12px;margin-bottom:14px}.adm header{border:0;background:transparent;padding:0}.adm header span{color:#67e8f9;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}.adm p,.adm small{color:#a7b5c8}.forms,.lists{display:grid;grid-template-columns:1fr 1fr;gap:10px}.adm article{display:grid;gap:8px;border:1px solid #31557f;background:#10223c;border-radius:14px;padding:10px}.adm section{display:grid;gap:3px;border-top:1px solid #294568;padding-top:8px}.adm input{border:1px solid #31557f;background:#030712;color:#e6edf7;border-radius:10px;padding:10px}.adm button{border:1px solid #31557f;background:#0f2746;color:#e6edf7;border-radius:10px;padding:8px}@media(max-width:900px){.forms,.lists{grid-template-columns:1fr}}`;
