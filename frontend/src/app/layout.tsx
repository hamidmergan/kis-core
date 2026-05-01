import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import FooterWrapper from "@/components/layout/FooterWrapper";
import LayoutShell from "@/components/layout/LayoutShell";
import MaintenanceGuard from "@/components/auth/MaintenanceGuard";
import NextTopLoader from "nextjs-toploader";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });

export const metadata: Metadata = {
  title: "KIS",
  description: "KIS - Services der TH Lübeck",
  authors: [{ name: "Hamid Mergan, Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck" }],
  other: {
    copyright: "© 2026 Hamid Mergan, Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck",
  },
};

// Set data-theme synchronously before React hydrates to prevent FOUC.
const themeBootScript = `(function(){try{var t=localStorage.getItem('kis.theme');if(t==='dark')document.documentElement.setAttribute('data-theme','dark');}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <head>
        <link rel="license" href="https://www.apache.org/licenses/LICENSE-2.0" />
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className={`${geist.variable} min-h-screen flex flex-col`}>
        <NextTopLoader color="#668DA0" showSpinner={false} height={3} />
        <MaintenanceGuard />
        <main className="flex-1">
          <LayoutShell>{children}</LayoutShell>
        </main>
        <FooterWrapper />
      </body>
    </html>
  );
}
