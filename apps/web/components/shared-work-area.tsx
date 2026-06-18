"use client";

import { WorkAreaBoard } from "@/components/work-area-board";
import type { DayControlLane } from "@/lib/day-control-work";
import { useDayControlStore } from "@/lib/day-control-store";

export function SharedWorkArea({ area, purpose, explanation, lanes }: { area: string; purpose: string; explanation: string; lanes: DayControlLane[] }) {
  const { rowsForLanes } = useDayControlStore();
  return <WorkAreaBoard area={area} purpose={purpose} explanation={explanation} rows={rowsForLanes(lanes)} />;
}
