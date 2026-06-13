"use client";

import { AuthGuard } from "@/components/auth-guard";
import { BvsPublicSiteBoard } from "@/components/bvs-public-site-board";
import { HospitalShell } from "@/components/hospital-shell";

export default function BvsPublicMapPage() {
  return <AuthGuard allow={["clinical_director", "ops_manager", "admin"]}><HospitalShell title="BVS PUBLIC MAP" subtitle="Public website operating model"><BvsPublicSiteBoard /></HospitalShell></AuthGuard>;
}
