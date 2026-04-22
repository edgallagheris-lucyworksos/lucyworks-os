"use client";

import { useEffect, useMemo, useState } from "react";
import { apiPost } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Section = {
  id: number;
  name: string;
  section_type: string;
};

type Room = {
  id: number;
  section_name: string;
  name: string;
  room_type: string;
};

export default function InputPage() {
  const [sections, setSections] = useState<Section[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [form, setForm] = useState({
    title: "",
    input_type: "email",
    source: "mail_ops",
    category: "communications",
    description: "",
    urgency: "amber",
    owner_role: "ops_manager",
    section_name: "Wards",
    room_name: "Ward Dogs",
    patient_location_label: "",
    linked_patient_name: "",
    linked_episode_ref: "",
  });
  const [result, setResult] = useState<string>("");

  useEffect(() => {
    async function loadTopology() {
      const [sectionsRes, roomsRes] = await Promise.all([
        fetch(`${API_BASE}/api/sections`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/rooms`, { cache: "no-store" }),
      ]);
      setSections(await sectionsRes.json());
      setRooms(await roomsRes.json());
    }
    loadTopology();
  }, []);

  const filteredRooms = useMemo(() => {
    return rooms.filter((room) => room.section_name === form.section_name);
  }, [rooms, form.section_name]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const created = await apiPost<{ id: number; title: string }>("/api/work-items", form);
    setResult(`Created work item #${created.id}: ${created.title}`);
    setForm({
      title: "",
      input_type: "email",
      source: "mail_ops",
      category: "communications",
      description: "",
      urgency: "amber",
      owner_role: "ops_manager",
      section_name: form.section_name,
      room_name: filteredRooms[0]?.name || "",
      patient_location_label: "",
      linked_patient_name: "",
      linked_episode_ref: "",
    });
  }

  function update(key: string, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  useEffect(() => {
    if (!filteredRooms.find((room) => room.name === form.room_name)) {
      setForm((prev) => ({ ...prev, room_name: filteredRooms[0]?.name || "" }));
    }
  }, [filteredRooms, form.room_name]);

  return (
    <main style={{ padding: 24, maxWidth: 980, margin: "0 auto" }}>
      <h1 style={{ fontSize: 36, marginTop: 0 }}>Unified Input</h1>
      <p style={{ color: "#94a3b8" }}>Turn an operational input into owned work in the correct hospital area.</p>
      <form onSubmit={onSubmit} style={{ display: "grid", gap: 12, marginTop: 20 }}>
        <input value={form.title} onChange={(e) => update("title", e.target.value)} placeholder="Title" required style={{ padding: 12, borderRadius: 12 }} />
        <textarea value={form.description} onChange={(e) => update("description", e.target.value)} placeholder="Description" required style={{ padding: 12, borderRadius: 12, minHeight: 120 }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
          <select value={form.input_type} onChange={(e) => update("input_type", e.target.value)} style={{ padding: 12, borderRadius: 12 }}>
            <option value="email">email</option>
            <option value="internal_message">internal_message</option>
            <option value="triage_note">triage_note</option>
            <option value="procedure_update">procedure_update</option>
            <option value="discharge_blocker">discharge_blocker</option>
            <option value="staffing_issue">staffing_issue</option>
          </select>
          <select value={form.source} onChange={(e) => update("source", e.target.value)} style={{ padding: 12, borderRadius: 12 }}>
            <option value="mail_ops">mail_ops</option>
            <option value="ward">ward</option>
            <option value="theatre">theatre</option>
            <option value="front_desk">front_desk</option>
          </select>
          <select value={form.urgency} onChange={(e) => update("urgency", e.target.value)} style={{ padding: 12, borderRadius: 12 }}>
            <option value="green">green</option>
            <option value="amber">amber</option>
            <option value="red">red</option>
          </select>
          <select value={form.owner_role} onChange={(e) => update("owner_role", e.target.value)} style={{ padding: 12, borderRadius: 12 }}>
            <option value="ops_manager">ops_manager</option>
            <option value="clinician">clinician</option>
            <option value="nurse">nurse</option>
            <option value="admin">admin</option>
          </select>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          <select value={form.section_name} onChange={(e) => update("section_name", e.target.value)} style={{ padding: 12, borderRadius: 12 }}>
            {sections.map((section) => (
              <option key={section.id} value={section.name}>{section.name}</option>
            ))}
          </select>
          <select value={form.room_name} onChange={(e) => update("room_name", e.target.value)} style={{ padding: 12, borderRadius: 12 }}>
            {filteredRooms.map((room) => (
              <option key={room.id} value={room.name}>{room.name}</option>
            ))}
          </select>
          <input value={form.patient_location_label} onChange={(e) => update("patient_location_label", e.target.value)} placeholder="Patient location / kennel / bay" style={{ padding: 12, borderRadius: 12 }} />
        </div>
        <input value={form.linked_patient_name} onChange={(e) => update("linked_patient_name", e.target.value)} placeholder="Patient name (optional)" style={{ padding: 12, borderRadius: 12 }} />
        <input value={form.linked_episode_ref} onChange={(e) => update("linked_episode_ref", e.target.value)} placeholder="Episode ref (optional)" style={{ padding: 12, borderRadius: 12 }} />
        <button type="submit" style={{ padding: 14, borderRadius: 12, background: "#14b8a6", color: "#020617", border: 0 }}>Create routed work item</button>
      </form>
      {result ? <p style={{ marginTop: 16 }}>{result}</p> : null}
    </main>
  );
}
