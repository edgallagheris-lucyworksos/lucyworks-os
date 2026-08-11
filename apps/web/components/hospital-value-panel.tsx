"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";

type Area = { areaRef: string; areaType: string; capacity: number };
type Block = { episodeRef?: string; startsAt: string; endsAt: string; areaRef: string; status: string };
type Episode = { episodeRef: string; status?: string };
type Board = {
  generatedAt: string;
  operationalDate: string;
  areas: Area[];
  blocks: Block[];
  episodes: Episode[];
  summary: {
    redConflicts: number;
    amberConflicts: number;
    unassignedBlocks: number;
    blockedBlocks: number;
  };
};

const PREMISES = "default-premises";
const BOOKABLE_TYPES = new Set(["theatre", "imaging", "consult", "prep", "recovery"]);
const OPERATING_MINUTES = 15 * 60;

function durationMinutes(block: Block) {
  const start = new Date(block.startsAt).getTime();
  const end = new Date(block.endsAt).getTime();
  return Math.max(0, Math.round((end - start) / 60_000));
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function HospitalValuePanel() {
  const [date, setDate] = useState(() => localOperationalDate());
  const [board, setBoard] = useState<Board | null>(null);
  const [status, setStatus] = useState("Loading operating signals");

  const refresh = useCallback(async () => {
    try {
      const currentDate = localOperationalDate();
      setDate(currentDate);
      const data = await apiGet<Board>(`/api/v11/master-board/day?premises_ref=${PREMISES}&operational_date=${currentDate}`);
      setBoard(data);
      setStatus(`Live ${new Date(data.generatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Operating signals unavailable");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const signals = useMemo(() => {
    if (!board) return null;
    const scheduledEpisodeRefs = new Set(board.blocks.map(block => block.episodeRef).filter(Boolean) as string[]);
    const activeEpisodes = board.episodes.filter(episode => episode.status !== "closed");
    const planned = activeEpisodes.filter(episode => scheduledEpisodeRefs.has(episode.episodeRef)).length;
    const flowCoverage = activeEpisodes.length ? planned / activeEpisodes.length : 1;

    const bookableAreas = board.areas.filter(area => BOOKABLE_TYPES.has(area.areaType));
    const bookableAreaRefs = new Set(bookableAreas.map(area => area.areaRef));
    const bookedMinutes = board.blocks
      .filter(block => bookableAreaRefs.has(block.areaRef) && !["cancelled", "void"].includes(block.status.toLowerCase()))
      .reduce((total, block) => total + durationMinutes(block), 0);
    const configuredMinutes = bookableAreas.reduce((total, area) => total + Math.max(1, area.capacity) * OPERATING_MINUTES, 0);
    const utilisation = configuredMinutes ? Math.min(1, bookedMinutes / configuredMinutes) : 0;

    return {
      patientRisk: board.summary.redConflicts,
      flowCoverage,
      unassigned: board.summary.unassignedBlocks,
      blocked: board.summary.blockedBlocks,
      utilisation,
      bookedMinutes,
    };
  }, [board]);

  return (
    <section className="hvp" aria-label="Hospital outcome and value signals">
      <style>{css}</style>
      <header>
        <div>
          <span>Hospital outcome & value</span>
          <h2>Care, client, staff and capacity</h2>
        </div>
        <div className="hvp-meta"><strong>{date}</strong><span>{status}</span></div>
      </header>

      {!signals ? <p className="hvp-loading">{status}</p> : <div className="hvp-grid">
        <article className={signals.patientRisk ? "risk" : "clear"}>
          <small>Patient</small>
          <strong>{signals.patientRisk}</strong>
          <span>red clinical conflicts</span>
          <p>Clinical risk remains the first constraint on every operational or commercial action.</p>
        </article>
        <article className={signals.flowCoverage < 1 ? "warn" : "clear"}>
          <small>Client / flow</small>
          <strong>{percent(signals.flowCoverage)}</strong>
          <span>active episodes with a planned block</span>
          <p>Better forward visibility reduces waiting, uncertainty and avoidable owner updates.</p>
        </article>
        <article className={signals.unassigned || signals.blocked ? "warn" : "clear"}>
          <small>Staff</small>
          <strong>{signals.unassigned + signals.blocked}</strong>
          <span>unassigned or blocked work items</span>
          <p>Ownership and blockers are exposed so pressure is resolved rather than carried invisibly.</p>
        </article>
        <article>
          <small>Commercial capacity</small>
          <strong>{percent(signals.utilisation)}</strong>
          <span>configured bookable minutes scheduled</span>
          <p>{signals.bookedMinutes.toLocaleString()} clinical minutes are currently planned. This is a utilisation signal, not a claimed profit margin.</p>
        </article>
      </div>}
    </section>
  );
}

const css = `
.hvp{margin:12px 18px 0;background:#fff;border:1px solid #d9e0e8;border-radius:14px;box-shadow:0 5px 18px rgba(15,23,42,.05);overflow:hidden;color:#172033}.hvp *{box-sizing:border-box}.hvp>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px 14px;background:#f8fafc;border-bottom:1px solid #e5eaf0}.hvp header span,.hvp small{display:block;color:#65758a;font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.hvp h2{margin:2px 0 0;font-size:17px;letter-spacing:-.01em}.hvp-meta{text-align:right}.hvp-meta strong{display:block;font-size:12px}.hvp-meta span{font-size:10px;letter-spacing:0;text-transform:none}.hvp-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:#e5eaf0}.hvp article{background:#fff;padding:13px 14px;border-top:3px solid #52738d}.hvp article.clear{border-top-color:#27855f}.hvp article.warn{border-top-color:#d18a16}.hvp article.risk{border-top-color:#c2413b}.hvp article>strong{display:block;margin-top:5px;font-size:24px;color:#17334d}.hvp article>span{display:block;color:#526174;font-size:11px;font-weight:700}.hvp article p{margin:7px 0 0;color:#718096;font-size:11px;line-height:1.4}.hvp-loading{margin:0;padding:14px;color:#65758a}
@media(max-width:900px){.hvp{margin:9px 12px 0}.hvp-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.hvp{margin:7px 7px 0}.hvp>header{align-items:flex-start}.hvp-meta{display:none}.hvp-grid{grid-template-columns:1fr 1fr}.hvp article{padding:10px}.hvp article>strong{font-size:20px}.hvp article p{display:none}}
`;