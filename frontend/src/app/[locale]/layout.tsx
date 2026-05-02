import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { cookies } from "next/headers";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import { setRequestLocale, getMessages, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import "../globals.css";
import FooterWrapper from "@/components/layout/FooterWrapper";
import LayoutShell from "@/components/layout/LayoutShell";
import MaintenanceGuard from "@/components/auth/MaintenanceGuard";
import NextTopLoader from "nextjs-toploader";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "layoutMeta" });
  return {
    title: t("title"),
    description: t("description"),
    authors: [{ name: t("author") }],
    other: { copyright: t("copyright") },
  };
}

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

// Backfills the kis-theme cookie from localStorage on first paint so SSR can
// pick it up after the next navigation. Cookie is the source of truth for SSR;
// localStorage stays for backwards-compat and cross-tab sync via storage events.
const themeBootScript = `(function(){try{var t=localStorage.getItem('kis.theme');var hasCookie=document.cookie.indexOf('kis-theme=')!==-1;if(t==='dark'){document.documentElement.setAttribute('data-theme','dark');if(!hasCookie)document.cookie='kis-theme=dark; path=/; max-age=31536000; SameSite=Lax';}else if(t==='light'&&!hasCookie){document.cookie='kis-theme=light; path=/; max-age=31536000; SameSite=Lax';}}catch(e){}})();`;

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
  const cookieStore = await cookies();
  const themeCookie = cookieStore.get("kis-theme")?.value;
  const dataTheme = themeCookie === "dark" ? "dark" : undefined;

  return (
    <html lang={locale} data-theme={dataTheme} suppressHydrationWarning>
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
