import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "DCAL Annotation Workbench",
  description: "Private document annotation workbench for DCAL.",
  robots: { index: false, follow: false, nocache: true },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
