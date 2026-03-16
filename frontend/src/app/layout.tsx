import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import Footer from "@/components/Footer";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });

export const metadata: Metadata = {
  title: "KIS",
  description: "KIS – Services der TH Lübeck",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className={`${geist.variable} min-h-screen flex flex-col`}>
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
