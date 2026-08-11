"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { apiGet } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";
import { getOperationalContext } from "@/lib/operational-context";

type EpisodeHit = { episodeRef: string; patientName: string; phase: string; urgency: string; ownerRole: string };
type Board = { episodes: EpisodeHit[] };

export function EpisodeCommandShell({ children }: { children: ReactNode }) {
  const [{ premisesRef, siteName }] = useState(() => getOperationalContext());
  const [episodeRef, setEpisodeRef] = useState("");
  const [query, setQuery] = useState("");
  const [episodes, setEpisodes] = useState<EpisodeHit[]>([]);

  useEffect(() => {
    const ref = new URLSearchParams(window.location.search).get("episode") || "";
    setEpisodeRef(ref);
  }, []);

  useEffect(() => {
    let active = true;
    async function loadPatients() {
      try {
        const board = await apiGet<Board>(`/api/v11/master-board/day?premises_ref=${encodeURIComponent(premisesRef)}&operational_date=${localOperationalDate()}`);
        if (active) setEpisodes(board.episodes || []);
      } catch {
        if (active) setEpisodes([]);
      }
    }
    void loadPatients();
    return () => { active = false; };
  }, [premisesRef]);

  const matches = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (term.length < 2) return [];
    return episodes.filter(row => [row.patientName, row.episodeRef, row.phase, row.ownerRole].some(value => value?.toLowerCase().includes(term))).slice(0, 6);
  }, [episodes, query]);

  function openEpisode(ref?: string) {
    const value = ref || query.trim();
    if (!value) return;
    const patientMatch = episodes.find(row => row.episodeRef.toLowerCase() === value.toLowerCase() || row.patientName.toLowerCase() === value.toLowerCase());
    window.location.assign(`/episode-command?episode=${encodeURIComponent(patientMatch?.episodeRef || value)}`);
  }

  return (
    <div className="episode-shell">
      <style>{css}</style>
      <header className="episode-shell__header">
        <div className="episode-shell__identity">
          <div className="episode-shell__mark">LW</div>
          <div><h1>Patient episode</h1><span>{siteName}</span></div>
        </div>
        <div className="episode-shell__finder">
          <div className="episode-shell__search">
            <span aria-hidden="true">⌕</span>
            <input aria-label="Find patient or episode" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === "Enter") openEpisode(); }} placeholder="Find patient or episode" autoComplete="off" />
            <button type="button" onClick={() => openEpisode()}>Open</button>
          </div>
          {matches.length ? <div className="episode-shell__results">{matches.map(row => <button type="button" key={row.episodeRef} onClick={() => openEpisode(row.episodeRef)}><strong>{row.patientName}</strong><span>{row.phase.replaceAll("_", " ")} · {row.ownerRole.replaceAll("_", " ")}</span></button>)}</div> : null}
        </div>
        <nav aria-label="Patient episode navigation">
          <Link href="/hospital-board">Hospital</Link>
          <Link href={episodeRef ? `/patient-record?episode=${encodeURIComponent(episodeRef)}` : "/patient-record"}>Record</Link>
          <Link href={episodeRef ? `/clinical-execution?episode=${encodeURIComponent(episodeRef)}` : "/clinical-execution"}>Clinical work</Link>
        </nav>
      </header>
      <div className="episode-shell__status">
        <span className="live" />
        <strong>{episodeRef ? "Episode open" : "No patient selected"}</strong>
        {episodeRef ? <span className="episode-shell__ref">{episodeRef}</span> : null}
      </div>
      {children}
    </div>
  );
}

const css = `
.episode-shell{min-height:100vh;background:#eef2f7;color:#172033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.episode-shell *{box-sizing:border-box}.episode-shell__header{position:sticky;top:0;z-index:50;display:grid;grid-template-columns:minmax(205px,1fr) minmax(300px,520px) auto;align-items:center;gap:14px;padding:10px 16px;background:rgba(255,255,255,.98);border-bottom:1px solid #d9e1e9;box-shadow:0 4px 16px rgba(15,23,42,.05);backdrop-filter:blur(14px)}.episode-shell__identity{display:flex;align-items:center;gap:10px}.episode-shell__mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:linear-gradient(145deg,#163a57,#102a42);color:#fff;font-size:11px;font-weight:900}.episode-shell__identity h1{margin:0;font-size:16px;line-height:1.1;color:#14283d}.episode-shell__identity span{display:block;margin-top:2px;color:#708095;font-size:9px;font-weight:700}.episode-shell__finder{position:relative}.episode-shell__search{display:flex;position:relative;gap:6px}.episode-shell__search>span{position:absolute;z-index:2;left:11px;top:8px;color:#76859a;font-size:18px}.episode-shell__search input{min-width:0;flex:1;height:38px;min-height:38px;border:1px solid #c4cfda;border-radius:8px;padding:0 10px 0 35px;background:#fff;color:#172033;font-size:12px}.episode-shell__search button{height:38px;min-height:38px;border:0;border-radius:8px;background:#173f5f;color:#fff;padding:0 13px;font-weight:800;font-size:11px}.episode-shell__results{position:absolute;left:0;right:55px;top:43px;z-index:60;display:grid;background:#fff;border:1px solid #ccd5df;border-radius:9px;box-shadow:0 14px 34px rgba(15,23,42,.15);overflow:hidden}.episode-shell__results button{display:grid;text-align:left;gap:2px;padding:9px 10px;min-height:0;border:0;border-bottom:1px solid #edf0f3;background:#fff;color:#172033}.episode-shell__results button:last-child{border-bottom:0}.episode-shell__results button:hover{background:#f4f7fa}.episode-shell__results strong{font-size:11px}.episode-shell__results span{color:#6d7c8e;font-size:9px;text-transform:capitalize}.episode-shell nav{display:flex;gap:3px}.episode-shell nav a{padding:7px 8px;border-radius:7px;color:#294761;text-decoration:none;font-size:10px;font-weight:750}.episode-shell nav a:hover{background:#edf2f7}.episode-shell__status{display:flex;align-items:center;gap:8px;min-height:32px;padding:6px 16px;background:#f8fafc;border-bottom:1px solid #dde4ec;color:#68778a;font-size:9px}.episode-shell__status .live{width:7px;height:7px;border-radius:999px;background:#27855f;box-shadow:0 0 0 3px #d9f0e5}.episode-shell__status strong{color:#273b50}.episode-shell__ref{color:#8793a2;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:8px}.episode-shell > main > header{display:none!important}.episode-shell > main{min-height:auto!important;padding-top:10px!important}
@media(max-width:900px){.episode-shell__header{grid-template-columns:1fr minmax(230px,390px);padding:9px 11px}.episode-shell nav{display:none}.episode-shell__status{padding:6px 11px}}
@media(max-width:560px){.episode-shell__header{grid-template-columns:1fr;gap:7px}.episode-shell__identity h1{font-size:15px}.episode-shell__identity span{font-size:9px}.episode-shell__mark{width:31px;height:31px}.episode-shell__search input,.episode-shell__search button{height:36px;min-height:36px}.episode-shell__results{right:52px;top:40px}.episode-shell__status .episode-shell__ref{display:none}}
`;
