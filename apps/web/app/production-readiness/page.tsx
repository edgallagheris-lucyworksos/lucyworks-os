"use client";

import { AuthGuard } from "@/components/auth-guard";
import { ProductionReadinessDashboard, seniorRoles } from "@/components/production-readiness-dashboard";

export default function ProductionReadinessPage() {
  return <AuthGuard allowedRoles={seniorRoles}>
    <ProductionReadinessDashboard />
  </AuthGuard>;
}
