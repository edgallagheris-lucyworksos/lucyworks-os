"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

const STORAGE_KEY = "lucyworks:selected-episode";
const EPISODE_ROUTES = new Set([
  "/care",
  "/patient-record",
  "/clinical-execution",
  "/episode-command",
  "/input",
  "/schedule",
]);

function selectedFromLocation(): string {
  return new URLSearchParams(window.location.search).get("episode")?.trim() || "";
}

export function EpisodeSelectionBridgeV31() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    const selected = selectedFromLocation();
    if (selected) {
      sessionStorage.setItem(STORAGE_KEY, selected);
      return;
    }

    const remembered = sessionStorage.getItem(STORAGE_KEY)?.trim() || "";
    if (remembered && EPISODE_ROUTES.has(pathname)) {
      router.replace(`${pathname}?episode=${encodeURIComponent(remembered)}`);
    }
  }, [pathname, router]);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const anchor = (event.target as Element | null)?.closest("a[href]") as HTMLAnchorElement | null;
      if (!anchor || anchor.target || anchor.hasAttribute("download")) return;
      const destination = new URL(anchor.href, window.location.href);
      if (destination.origin !== window.location.origin || !EPISODE_ROUTES.has(destination.pathname) || destination.searchParams.has("episode")) return;
      const selected = selectedFromLocation() || sessionStorage.getItem(STORAGE_KEY)?.trim() || "";
      if (selected) anchor.href = `${destination.pathname}?episode=${encodeURIComponent(selected)}${destination.hash}`;
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  return null;
}
