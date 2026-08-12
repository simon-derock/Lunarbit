import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import { ProfileProvider } from "@/components/ProfileProvider";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Lunarbit — Personal Commerce Intelligence",
  description:
    "An evidence-verifiable personal commerce GraphRAG and economic intelligence system.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <ProfileProvider>
          <AppShell>{children}</AppShell>
        </ProfileProvider>
      </body>
    </html>
  );
}
