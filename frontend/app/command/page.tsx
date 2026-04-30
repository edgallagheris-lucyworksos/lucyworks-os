"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { DomainAutomationPanel } from "@/components/domain-automation-panel";
import { DomainPressurePanel } from "@/components/domain-pressure-panel";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type DirectorCard = { key: string; label: string; value: number; tone: string };
type SectionPressure = { section_name: string; live: number; red: number; unowned: number };
type WorkItem = { id: number; title: string; urgency: string; owner_role: string; status: string; section_name?: string | null; room_name?: string | null; patient_location_label?: string | null; linked_patient_name?: string | null; linked_episode_ref?: string | null };
type DirectorBoard = { cards: DirectorCard[]; section_pressure: SectionPressure[]; priority_items: WorkItem[] };

function toneBorder(tone: string): string {
  if (tone === "critical") return "1px solid #7f1d1d";
  if (tone === "warning") return "1px solid #78350f";
  if (tone === "stable") return "1px solid #14532d";
  if (tone === "info") return "1px solid #1e3a8a";
  return "1px solid #1f2937";
}

function commandRead(board: DirectorBoard) {
  const red = board.priority_items.filter((i) => i.urgency === "red" && i.status !== "done");
  const newItems = board.priority_items.filter((i) => i.status === "new");
  const highest = [...board.section_pressure].sort((a, b) => (b.red * 3 + b.live + b.unowned) - (a.red * 3 + a.live + a.unowned))[0];
  const lead = red[0] || newItems[0] || board.priority_items[0];
  return {
    risk: red.length ? "red" : newItems.length ? "amber" : "green",
    highest,
    lead,
    action: lead?.linked_episode_ref ? `/episodes/${lead.linked_episode_ref}` : highest ? "/queues" : "/system",
    summary: red.length
      ? `${red.length} red item(s) need owner-led clearance before safe flow improves.`
      : newItems.length
        ? `${newItems.length} new item(s) need assignment before they become drift.`
        : "No urgent command items. Maintain flow and clear low-level pressure.",
  };
}

function CommandInner() {
  const [board, setBoard] = useState<DirectorBoard | null>(null);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/director-board`, { cache: "no-store" });
      setBoard(await res.json());
    }
    load();
  }, []);

  const read = useMemo(() => board ? commandRead(board) : null, [board]);

  return (
    <HospitalShell title="Clinical Director / Command" subtitle="What matters, who owns it, and what happens next">
      {!board ? <p>Loading command board...</p> : null}
      {board && read ? (
        <>
          <section className="lw-card" style={{ border: toneBorder(read.risk === "red" ? "critical" : read.risk === "amber" ? "warning" : "stable"), padding: 20, marginBottom: 16 }}>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Command read</div>
            <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr auto", gap: 16, alignItems: "end", marginTop: 10 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 32 }}>Hospital control state: {read.risk.toUpperCase()}</h2>
                <p style={{ color: "#94a3b8", marginBottom: 0 }}>{read.summary}</p>
              </div>
              <div style={{ color: "#cbd5e1" }}>
                <strong>Highest section pressure</strong>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{read.highest ? `${read.highest.section_name}: live ${read.highest.live}, red ${read.highest.red}, unowned ${read.highest.unowned}` : "No section pressure"}</div>
              </div>
              <Link href={read.action} className="lw-btn-primary" style={{ borderRadius: 14, padding: "12px 14px", textAlign: "center" }}>Open next action</Link>
            </div>
            {read.lead ? <div style={{ borderTop: "1px solid #1f2937", marginTop: 16, paddingTop: 14, color: "#94a3b8" }}><strong style={{ color: "#f8fafc" }}>Lead item:</strong> {read.lead.title} • owner {read.lead.owner_role} • {read.lead.urgency}/{read.lead.status} {read.lead.linked_episode_ref ? `• episode ${read.lead.linked_episode_ref}` : ""}</div> : null}
          </section>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
            <DomainAutomationPanel />
            <DomainPressurePanel />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12, marginTop: 16 }}>
            {board.cards.map((card) => (
              <div key={card.key} className="lw-card" style={{ border: toneBorder(card.tone), padding: 16 }}>
                <div style={{ color: "#94a3b8", fontSize: 14 }}>{card.label}</div>
                <div style={{ fontSize: 34, fontWeight: 900, marginTop: 8 }}>{card.value}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.2fr) minmax(320px, 1fr)", gap: 16, marginTop: 24 }}>
            <section className="lw-card" style={{ overflow: "hidden" }}>
              <div style={{ padding: 16, background: "#0f172a", fontWeight: 800 }}>Priority board — decision/action spine</div>
              <div>
                {board.priority_items.map((item) => (
                  <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                      <strong>{item.title}</strong>
                      <span>{item.urgency.toUpperCase()} / {item.status}</span>
                    </div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>
                      {item.section_name ? `section: ${item.section_name} • ` : ""}
                      {item.room_name ? `room: ${item.room_name} • ` : ""}
                      {item.patient_location_label ? `location: ${item.patient_location_label} • ` : ""}
                      {item.linked_patient_name ? `patient: ${item.linked_patient_name} • ` : ""}
                      owner: {item.owner_role} {item.linked_episode_ref ? `• episode: ${item.linked_episode_ref}` : ""}
                    </div>
                    <div style={{ color: "#94a3b8", marginTop: 8 }}>Next action: assign or clear this item, then confirm the linked episode flow-readiness state.</div>
                    {item.linked_episode_ref ? <div style={{ marginTop: 8 }}><Link href={`/episodes/${item.linked_episode_ref}`}>Open episode command</Link></div> : null}
                  </div>
                ))}
              </div>
            </section>

            <section className="lw-card" style={{ overflow: "hidden" }}>
              <div style={{ padding: 16, background: "#0f172a", fontWeight: 800 }}>Section pressure — where delay compounds</div>
              <div>
                {board.section_pressure.map((section) => (
                  <div key={section.section_name} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                      <strong>{section.section_name}</strong>
                      <span>live {section.live}</span>
                    </div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>red {section.red} • unowned {section.unowned}</div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>Interpretation: red = unsafe drift; unowned = no accountable person; live = work volume.</div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </>
      ) : null}
    </HospitalShell>
  );
}

export default function CommandPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinician"]}>{() => <CommandInner />}</AuthGuard>;
}
