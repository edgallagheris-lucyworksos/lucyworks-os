"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { clearSession, getSession, type SessionUser } from "@/lib/session";
import { DailyOperationalBoard } from "@/components/daily-operational-board";
import { ResourceControlBoard } from "@/components/resource-control-board";
import { BvsClinicalServiceBoard } from "@/components/bvs-clinical-service-board";
import {
  ClinicalDirectorDashboard,
  InterruptionsDashboard,
  MyShiftDashboard,
  PatientFlowDashboard,
} from "@/components/hospital-operational-screens";
import { moduleByTitle, primaryHospitalModules, secondaryHospitalModules } from "@/lib/hospital-modules";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
type AlertSummary = { total_alerts: number; high_alerts: number };

function contentFor(title: string, children: ReactNode, user: SessionUser | null) {
  const module = moduleByTitle(title);
  const u = user || undefined;
  if (module?.id === "now") return <DailyOperationalBoard />;
  if (module?.id === "flow") return <PatientFlowDashboard user={u} />;
  if (module?.id === "ops") return <ResourceControlBoard />;
  if (module?.id === "clinical") return <BvsClinicalServiceBoard />;
  if (module?.id === "hr") return <MyShiftDashboard user={u} />;
  if (module?.id === "pulse") return <InterruptionsDashboard user={u} />;
  if (title === "Manager") return <ClinicalDirectorDashboard user={u} />;
  if (module?.id === "care" || module?.id === "move") return <MyShiftDashboard user={u} />;
  return children;
}

export function HospitalShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [alerts, setAlerts] = useState<AlertSummary>({ total_alerts: 0, high_alerts: 0 });

  useEffect(() => {
    const session = getSession();
    setUser(session?.user || null);
    async function loadAlerts() {
      try {
        const res = await fetch(`${API_BASE}/api/alerts`, { cache: "no-store" });
        const data = await res.json();
        setAlerts({ total_alerts: data.total_alerts || 0, high_alerts: data.high_alerts || 0 });
      } catch {
        setAlerts({ total_alerts: 0, high_alerts: 0 });
      }
    }
    loadAlerts();
  }, []);

  return (
    <main className="lw-shell lw-cinematic-bg">
      <div className="lw-topbar lw-glass-topbar">
        <div className="lw-wrap">
          <div className="lw-brand-row">
            <Link href="/hospital-board" className="lw-brand-title lw-wordmark-link">
              <span className="lw-orbit-mark small"><span /></span>
              <span>
                <span className="lw-product lw-wordmark">lucyworks</span>
                <span className="lw-subtitle">Operational Integrity OS • {title} • {subtitle}</span>
              </span>
            </Link>
            <div className="lw-actions">
              {user ? <span className="lw-pill">{user.name} • {user.role}</span> : <Link className="lw-pill" href="/login">Login</Link>}
              <Link href="/alerts" className={alerts.high_alerts ? "lw-pill lw-alert-pill" : "lw-pill"}>Alerts {alerts.total_alerts} / high {alerts.high_alerts}</Link>
              <Link href="/system-control" className="lw-pill">System</Link>
              <button onClick={() => { clearSession(); window.location.href = "/login"; }} className="lw-pill">Sign out</button>
            </div>
          </div>
          <div className="lw-nav lw-primary-nav">
            {primaryHospitalModules.map((item) => <Link key={item.id} href={item.route}>{item.label}</Link>)}
            <Link href="/manager-dashboard">Manager</Link>
          </div>
          <div className="lw-nav lw-secondary-nav">
            {secondaryHospitalModules.map((item) => <Link key={item.id} href={item.route}>{item.label}</Link>)}
          </div>
        </div>
      </div>
      <div className="lw-main">{contentFor(title, children, user)}</div>
    </main>
  );
}
