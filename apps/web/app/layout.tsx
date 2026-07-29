import "./globals.css";
import "./lucyworks-visual.css";
import "./accessibility.css";
import type { Metadata } from "next";
import { OperatingContextV26Bar } from "@/components/operating-context-v26-bar";

export const metadata: Metadata = {
  title: "LucyWorks OS",
  description: "Hospital command system",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">Skip to main content</a>
        <OperatingContextV26Bar />
        <div id="main-content">{children}</div>
      </body>
    </html>
  );
}
