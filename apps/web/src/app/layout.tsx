import type { Metadata } from "next";
import { AppHeader } from "@/components/app-header";
import "./globals.css";

export const metadata: Metadata = {
  title: "DealMind",
  description: "Service health and infrastructure diagnostics for DealMind.",
  icons: { icon: "/icon.svg" },
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip" href="#content">
          Skip to overview
        </a>
        <AppHeader />
        {children}
      </body>
    </html>
  );
}
