"use client";

import { AuthGuard } from "@/components/auth-guard";
import { ComplianceSafetyWorkspace, complianceSafetyRoles } from "@/components/compliance-safety-workspace";

export default function ComplianceSafetyPage() {
  return <AuthGuard allowedRoles={complianceSafetyRoles}>
    <ComplianceSafetyWorkspace />
  </AuthGuard>;
}
