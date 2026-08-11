"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";
import { getOperationalContext } from "@/lib/operational-context";

type Area = { areaRef: string; areaType: string; capacity: number };
type Block = { episodeRef?: string; startsAt: string; endsAt: string; areaRef: string; status: string };
type Episode = { episodeRef: string; status?: string };
type Board = {
  generatedAt: string;
  areas: Area[];
  blocks: Block[];
  episodes: Episode[];
  summary: { redConflicts: number; unassignedBlocks: number; blockedBlocks: number };
};

const BOOKABLE_TYPES = new Set(["theatre", "imaging", "consult", "prep", "recovery"]);
const OPERATING_MINUTES = 15 * 60;

function durationMinutes(block: Block) {
  return Math.max(0, Math.round((new Date(block.endsAt).getTime() - new Date(block.startsAt).getTime()) / 60_000));
}

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function HospitalValuePanel() {
  const [{ premisesRef }] = useState(() => getOperationalContext());
  const [board, setBoard] = useState<Board | null>(null);
  const [available, setAvailable] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const date = localOperationalDate();
      const data = await apiGet<Board>(`/api/v11/master-board/day?premises_ref=${encodeURIComponent(premisesRef)}&operational_date=${date}`);
      setBoard(data);
      setAvailable(true);
    } catch {
      setAvailable(false);
    }
  }, [premisesRef]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const signals = useMemo(() => {
    if (!board) return null;
    const scheduled = new Set(board.blocks.map(block => block.episodeRef).filter(Boolean) as string[]);
    const active = board.episodes.filter(episode => episode.status !== "closed");
    const flowCoverage = active.length ? active.filter(episode => scheduled.has(episode.episodeRef)).length / active.length : 1;
    const areas = board.areas.filter(area => BOOKABLE_TYPES.has(area.areaType));
    const areaRefs = new Set(areas.map(area => area.areaRef));
    const booked = board.blocks.filter(block => areaRefs.has(block.areaRef) && !["cancelled", "void"].includes(block.status.toLowerCase())).reduce((total, block) => total + durationMinutes(block), 0);
    const availableMinutes = areas.reduce((total, area) => total + Math.max(1, area.capacity) * OPERATING_MINUTES, 0);
    return {
      clinical: board.summary.redConflicts,
      flow: flowCoverage,
      staff: board.summary.unassignedBlocks + board.summary.blockedBlocks,
      utilisation: availableMinutes ? Math.min(1, booked / availableMinutes) : 0,
    };
  }, [board]);

  if (!available) return null;

  return (
    <section className="value-strip" aria-label="Hospital operating indicators">
      <style>{css}</style>
      <div className="value-strip__title"><span>Operating indicators</span><strong>Today</strong></div>
      <article className={signals?.clinical ? "bad" : "good"}><span>Clinical exceptions</span><strong>{signals?.clinical ?? "—"}</strong></article>
      <article className={(signals?.flow ?? 1) < 1 ? "warn" : "good"}><span>Patients with planned care</span><strong>{signals ? pct(signals.flow) : "—"}</strong></article>
      <article className={signals?.staff ? "warn" : "good"}><span>Blocked / unassigned</span><strong>{signals?.staff ?? "—"}</strong></article>
      <article><span>Bookable capacity scheduled</span><strong>{signals ? pct(signals.utilisation) : "—"}</strong></article>
    </section>
  );
}

const css = `
.value-strip{display:grid;grid-template-columns:190px repeat(4,minmax(0,1fr));margin:12px 18px 0;background:#fff;border:1px solid #d9e1e9;border-radius:11px;overflow:hidden;color:#172033;font-family:Inter,ui-sans-serif,system-ui,sans-serif}.value-strip *{box-sizing:border-box}.value-strip__title,.value-strip article{display:grid;align-content:center;gap:2px;min-height:68px;padding:10px 12px;border-right:1px solid #e8edf2}.value-strip article:last-child{border-right:0}.value-strip__title{background:#f7f9fb}.value-strip span{color:#69798c;font-size:9px;font-weight:800;letter-spacing:.05em;text-transform:uppercase}.value-strip__title strong{font-size:13px}.value-strip article strong{font-size:20px;color:#17334d;letter-spacing:-.03em}.value-strip article{border-top:3px solid #52738d}.value-strip article.good{border-top-color:#2d8061}.value-strip article.warn{border-top-color:#c27a16}.value-strip article.bad{border-top-color:#b9403a}
@media(max-width:900px){.value-strip{grid-template-columns:repeat(4,1fr);margin:9px 12px 0}.value-strip__title{display:none}.value-strip article{min-height:62px}}
@media(max-width:560px){.value-strip{grid-template-columns:1fr 1fr;margin:7px 8px 0}.value-strip article:nth-child(3){border-right:0}.value-strip article{min-height:58px;padding:8px 9px}.value-strip article strong{font-size:18px}}
`;
