"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

export function EpisodeCommandShell({ children }: { children: ReactNode }) {
  const [episodeRef, setEpisodeRef] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    const ref = new URLSearchParams(window.location.search).get("episode") || "";
    setEpisodeRef(ref);
    setQuery(ref);
  }, []);

  function openEpisode() {
    const value = query.trim();
    if (!value) return;
    window.location.assign(`/episode-command?episode=${encodeURIComponent(value)}`);
  }

  return (
    <div className="episode-shell">
      <style>{css}</style>
      <header className="episode-shell__header">
        <div className="episode-shell__identity">
          <div className="episode-shell__mark">LW</div>
          <div>
            <span>LucyWorks OS</span>
            <h1>Patient episode control</h1>
          </div>
        </div>
        <div className="episode-shell__search">
          <input
            aria-label="Episode reference"
            value={query}
            onChange={event => setQuery(event.target.value)}
            onKeyDown={event => { if (event.key === "Enter") openEpisode(); }}
            placeholder="Episode reference"
          />
          <button type="button" onClick={openEpisode}>Open</button>
        </div>
        <nav aria-label="Patient episode navigation">
          <Link href="/hospital-board">Hospital</Link>
          <Link href={episodeRef ? `/patient-record?episode=${encodeURIComponent(episodeRef)}` : "/patient-record"}>Record</Link>
          <Link href={episodeRef ? `/clinical-execution?episode=${encodeURIComponent(episodeRef)}` : "/clinical-execution"}>Clinical work</Link>
        </nav>
      </header>
      <div className="episode-shell__status">
        <span className="live" />
        <strong>{episodeRef ? `Episode ${episodeRef}` : "Select an episode"}</strong>
        <span>Clinical state, authority, client communication, evidence and financial controls share one patient context.</span>
      </div>
      {children}
    </div>
  );
}

const css = `
.episode-shell{min-height:100vh;background:#e9eef5;color:#172033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.episode-shell *{box-sizing:border-box}.episode-shell__header{position:sticky;top:0;z-index:50;display:grid;grid-template-columns:minmax(220px,1fr) minmax(260px,430px) auto;align-items:center;gap:16px;padding:11px 16px;background:rgba(255,255,255,.98);border-bottom:1px solid #d9e0e8;box-shadow:0 4px 16px rgba(15,23,42,.05);backdrop-filter:blur(12px)}.episode-shell__identity{display:flex;align-items:center;gap:10px}.episode-shell__mark{display:grid;place-items:center;width:35px;height:35px;border-radius:9px;background:#12314f;color:white;font-size:12px;font-weight:900}.episode-shell__identity span{display:block;color:#65758a;font-size:9px;font-weight:850;letter-spacing:.12em;text-transform:uppercase}.episode-shell__identity h1{margin:1px 0 0;font-size:17px;line-height:1.1;color:#14283d}.episode-shell__search{display:flex;gap:6px}.episode-shell__search input{min-width:0;flex:1;height:38px;border:1px solid #b9c5d2;border-radius:8px;padding:0 10px;background:white;color:#172033;font-size:13px}.episode-shell__search button{height:38px;border:0;border-radius:8px;background:#173f5f;color:white;padding:0 13px;font-weight:800;cursor:pointer}.episode-shell nav{display:flex;gap:4px}.episode-shell nav a{padding:7px 8px;border-radius:7px;color:#294761;text-decoration:none;font-size:11px;font-weight:750}.episode-shell nav a:hover{background:#edf2f7}.episode-shell__status{display:flex;align-items:center;gap:8px;min-height:34px;padding:6px 16px;background:#f8fafc;border-bottom:1px solid #dde4ec;color:#68778a;font-size:10px}.episode-shell__status .live{width:7px;height:7px;border-radius:999px;background:#27855f;box-shadow:0 0 0 3px #d9f0e5}.episode-shell__status strong{color:#273b50}.episode-shell__status span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* The historical workspace header contains implementation-version language. The professional shell above replaces it while preserving the tested command controls below. */
.episode-shell > main > header{display:none!important}.episode-shell > main{min-height:auto!important;padding-top:10px!important}
@media(max-width:900px){.episode-shell__header{grid-template-columns:1fr minmax(220px,360px);padding:9px 11px}.episode-shell nav{display:none}.episode-shell__status{padding:6px 11px}.episode-shell__status span:last-child{display:none}}
@media(max-width:560px){.episode-shell__header{grid-template-columns:1fr;gap:7px}.episode-shell__identity h1{font-size:15px}.episode-shell__identity span{display:none}.episode-shell__mark{width:31px;height:31px}.episode-shell__search input,.episode-shell__search button{height:36px}}
`;
