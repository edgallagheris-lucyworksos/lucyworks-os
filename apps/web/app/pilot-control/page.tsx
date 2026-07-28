"use client";

import { AuthGuard } from "@/components/auth-guard";
import { BoundedPilotControlV24, pilotControlRoles } from "@/components/bounded-pilot-control-v24";

export default function PilotControlPage() {
  return <AuthGuard allowedRoles={pilotControlRoles}>
    <BoundedPilotControlV24 />
  </AuthGuard>;
}
