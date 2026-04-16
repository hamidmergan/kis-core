import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import FooterWrapper from "@/components/layout/FooterWrapper";
import FullscreenClass from "@/components/layout/FullscreenClass";
import MaintenanceGuard from "@/components/auth/MaintenanceGuard";
import NextTopLoader from "nextjs-toploader";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });

export const metadata: Metadata = {
  title: "KIS",
  description: "KIS – Services der TH Lübeck",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className={`${geist.variable} min-h-screen flex flex-col`}>
        <NextTopLoader color="#668DA0" showSpinner={false} height={3} />
        <FullscreenClass />
        <MaintenanceGuard />
        <main className="flex-1">{children}</main>
        <FooterWrapper />
        <div className="rotate-hint" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
            <line x1="12" y1="18" x2="12" y2="18" />
          </svg>
          <p>Bitte Gerät hochkant drehen</p>
        </div>
      </body>
    </html>
  );
}
