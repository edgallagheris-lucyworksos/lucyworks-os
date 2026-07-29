"use client";

import { AuthGuard } from "@/components/auth-guard";
import { CrossSystemSafetyControlV25, safetyControlRoles } from "@/components/cross-system-safety-control-v25";

export default function SafetyControlPage() {
  return <AuthGuard allowedRoles={safetyControlRoles}>
    <CrossSystemSafetyControlV25 />
  </AuthGuard>;
}
