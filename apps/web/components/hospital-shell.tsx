"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  ClinicalDirectorDashboard,
  HospitalCommandDashboard,
  InterruptionsDashboard,
  MyShiftDashboard,
  PatientFlowDashboard,
  ResourcesDashboard,
} from "@/components/hospital-operational-screens";

function contentFor(title: string, children: ReactNode) {
  if (title === "NOW") return <HospitalCommandDashboard />;
  if (title === "FLOW") return <PatientFlowDashboard />;
  if (title === "RESOURCES") return <ResourcesDashboard />;
  if (title === "MY SHIFT") return <MyShiftDashboard />;
  if (title === "INTERRUPTS") return <InterruptionsDashboard />;
  if (title === "Manager") return <ClinicalDirectorDashboard />;
  if (title === "Nurse") return <MyShiftDashboard />;
  if (title === "PCA") return <MyShiftDashboard />;
  return children;
}

export function HospitalShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
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
              <Link className="lw-pill" href="/login">Login</Link>
              <Link href="/alerts" className="lw-pill">Alerts</Link>
              <Link href="/system-control" className="lw-pill">System</Link>
            </div>
          </div>
          <div className="lw-nav lw-primary-nav">
            <Link href="/hospital-board">NOW</Link>
            <Link href="/flow">LucyFlow</Link>
            <Link href="/resources">LucyOps</Link>
            <Link href="/my-shift">LucyHR</Link>
            <Link href="/interrupts">LucyPulse</Link>
            <Link href="/manager-dashboard">Manager</Link>
          </div>
        </div>
      </div>
      <div className="lw-main">{contentFor(title, children)}</div>
    </main>
  );
}
