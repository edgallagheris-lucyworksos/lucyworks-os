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
import { moduleByTitle, primaryHospitalModules, secondaryHospitalModules } from "@/lib/hospital-modules";

function contentFor(title: string, children: ReactNode) {
  const module = moduleByTitle(title);
  if (module?.id === "now") return <HospitalCommandDashboard />;
  if (module?.id === "flow") return <PatientFlowDashboard />;
  if (module?.id === "ops") return <ResourcesDashboard />;
  if (module?.id === "hr") return <MyShiftDashboard />;
  if (module?.id === "pulse") return <InterruptionsDashboard />;
  if (title === "Manager") return <ClinicalDirectorDashboard />;
  if (module?.id === "care" || module?.id === "move") return <MyShiftDashboard />;
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
            {primaryHospitalModules.map((item) => <Link key={item.id} href={item.route}>{item.label}</Link>)}
            <Link href="/manager-dashboard">Manager</Link>
          </div>
          <div className="lw-nav lw-secondary-nav">
            {secondaryHospitalModules.map((item) => <Link key={item.id} href={item.route}>{item.label}</Link>)}
          </div>
        </div>
      </div>
      <div className="lw-main">{contentFor(title, children)}</div>
    </main>
  );
}
