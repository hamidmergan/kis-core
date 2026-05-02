import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import { setRequestLocale, getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import "../globals.css";
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

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

const themeBootScript = `(function(){try{var t=localStorage.getItem('kis.theme');if(t==='dark')document.documentElement.setAttribute('data-theme','dark');}catch(e){}})();`;

type Props = {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
};

export default async function RootLayout({ children, params }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <link rel="license" href="https://www.apache.org/licenses/LICENSE-2.0" />
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className={`${geist.variable} min-h-screen flex flex-col`}>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <NextTopLoader color="#668DA0" showSpinner={false} height={3} />
          <MaintenanceGuard />
          <main className="flex-1">
            <LayoutShell>{children}</LayoutShell>
          </main>
          <FooterWrapper />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
