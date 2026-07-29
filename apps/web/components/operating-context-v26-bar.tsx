"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Context = {
  contextRef: string;
  organisationRef: string;
  siteRef: string;
  premisesRef: string;
  version: number;
};

type Site = {
  organisationRef: string;
  siteRef: string;
  premisesRef: string;
  name: string;
  configurationState: string;
  role: string;
};

type ContextPayload = { context: Context; sites: Site[] };
type OperationalView = {
  summary: {
    activeImpacts: number;
    openCommands: number;
    affectedPatients: number;
    severityCounts: Record<string, number>;
  };
};

export function OperatingContextV26Bar() {
  const pathname = usePathname();
  const [data, setData] = useState<ContextPayload | null>(null);
  const [view, setView] = useState<OperationalView | null>(null);
  const [error, setError] = useState("");
  const [switching, setSwitching] = useState(false);

  async function load() {
    if (pathname.startsWith("/login")) return;
    try {
      const [context, operational] = await Promise.all([
        apiGet<ContextPayload>("/api/v26/context"),
        apiGet<OperationalView>("/api/v26/operational-view"),
      ]);
      setData(context);
      setView(operational);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Operating context unavailable");
    }
  }

  useEffect(() => {
    void load();
  }, [pathname]);

  if (pathname.startsWith("/login")) return null;
  if (!data) {
    return error ? (
      <div role="alert" style={{ padding: "7px 12px", background: "#7f1d1d", color: "white", fontWeight: 800 }}>
        Hospital context unavailable: {error}
      </div>
    ) : null;
  }

  async function switchSite(siteRef: string) {
    if (!data || !siteRef || siteRef === data.context.siteRef) return;
    const expectedVersion = data.context.version;
    setSwitching(true);
    try {
      await apiPost("/api/v26/context/switch", {
        siteRef,
        expectedVersion,
        reason: "User selected a different authorised hospital site.",
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Site switch failed");
    } finally {
      setSwitching(false);
    }
  }

  const counts = view?.summary;
  const red = counts?.severityCounts?.red || 0;
  const critical = counts?.severityCounts?.critical || 0;

  return (
    <aside aria-label="Active hospital operating context" style={{ position: "sticky", top: 0, zIndex: 60, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 9, padding: "8px 12px", background: critical || red ? "#450a0a" : "#071019", color: "white", borderBottom: "1px solid #334155" }}>
      <strong style={{ letterSpacing: ".06em" }}>ACTIVE HOSPITAL</strong>
      <select
        aria-label="Select authorised hospital site"
        value={data.context.siteRef}
        disabled={switching || data.sites.length < 2}
        onChange={(event) => void switchSite(event.target.value)}
        style={{ minHeight: 34, borderRadius: 8, padding: "4px 8px", fontWeight: 800 }}
      >
        {data.sites.map((site) => (
          <option key={site.siteRef} value={site.siteRef}>{site.name} · {site.premisesRef}</option>
        ))}
      </select>
      <span style={{ color: "#cbd5e1" }}>Org: {data.context.organisationRef}</span>
      <span style={{ color: "#cbd5e1" }}>Context v{data.context.version}</span>
      <span style={{ marginLeft: "auto", fontWeight: 800 }}>
        {counts?.activeImpacts || 0} active impacts · {counts?.affectedPatients || 0} affected patients · {counts?.openCommands || 0} open commands
      </span>
      {(critical > 0 || red > 0) && <strong style={{ color: "#fecaca" }}>{critical} critical · {red} red</strong>}
      <Link href="/operating-context" style={{ color: "#5eead4", fontWeight: 900 }}>Open context control →</Link>
    </aside>
  );
}
