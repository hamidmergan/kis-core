import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import FooterWrapper from "@/components/FooterWrapper";
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
        <main className="flex-1">{children}</main>
        <FooterWrapper />
      </body>
    </html>
  );
}
