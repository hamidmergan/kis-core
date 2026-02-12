import type { Metadata } from "next";
import "./globals.css";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "KIS-THL",
  description: "KIS-THL – Services der TH Lübeck",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className="min-h-screen bg-gray-50 flex flex-col font-[system-ui,-apple-system,BlinkMacSystemFont,'Segoe_UI',Roboto,sans-serif]">
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
