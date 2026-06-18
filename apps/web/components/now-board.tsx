"use client";

import { DayControlGrid } from "@/components/day-control-grid";
import { ScheduleWarningsPanel } from "@/components/schedule-warnings-panel";

export function NowBoard() {
  return <><ScheduleWarningsPanel /><DayControlGrid /></>;
}
