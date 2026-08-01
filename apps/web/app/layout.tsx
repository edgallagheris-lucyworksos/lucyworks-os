import "./globals.css";
import "./lucyworks-visual.css";
import "./accessibility.css";
import type { Metadata } from "next";
import { OperatingContextV26Bar } from "@/components/operating-context-v26-bar";
import { EpisodeSelectionBridgeV31 } from "@/components/episode-selection-bridge-v31";
import { TechnicalSurfaceBoundaryV31 } from "@/components/technical-surface-boundary-v31";

export const metadata: Metadata = {
  title: "LucyWorks OS",
  description: "Hospital command system",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">Skip to main content</a>
        <EpisodeSelectionBridgeV31 />
        <OperatingContextV26Bar />
        <TechnicalSurfaceBoundaryV31 />
        <div id="main-content">{children}</div>
      </body>
    </html>
  );
}
