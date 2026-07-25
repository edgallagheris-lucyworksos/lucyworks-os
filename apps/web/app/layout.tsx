import "./globals.css";
import "./lucyworks-visual.css";
import "./accessibility.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "LucyWorks OS",
  description: "Hospital command system",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">Skip to main content</a>
        <div id="main-content">{children}</div>
      </body>
    </html>
  );
}
