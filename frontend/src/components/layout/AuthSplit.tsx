"use client";

/** Two-column frame of the public sign-in pages, Francis on the left and the form on the right. */

import { useTranslations } from "next-intl";
import Header from "@/components/layout/Header";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";

type Props = {
  heading: string;
  hideLogin?: boolean;
  children: React.ReactNode;
};

export default function AuthSplit({ heading, hideLogin = false, children }: Props) {
  const t = useTranslations("login");
  const { variant } = useMascotPref();

  return (
    <div className="flex flex-col lg:min-h-dvh">
      <Header hasSession={false} showLogout hideLogin={hideLogin} />
      <main className="grid lg:flex-1 lg:grid-cols-[5fr_6fr]">
        <h1 className="sr-only">{heading}</h1>
        <section className="relative hidden lg:flex items-center justify-center bg-kb px-14 py-14">
          <div className="flex w-full max-w-md flex-col items-center">
            <div className="relative">
              <span
                aria-hidden="true"
                className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-72 w-72 rounded-full border-2 border-white/15"
              />
              <span
                aria-hidden="true"
                className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-52 w-52 rounded-full bg-white/10"
              />
              <div className="relative"><Mascot variant={variant} size={200} state="wave" /></div>
            </div>
            <div className="mt-16 text-center">
              <p className="text-2xl font-semibold leading-snug text-on-accent">{t("francisName")}</p>
              <p className="mt-1 text-base text-on-accent/80">{t("francisRole")}</p>
            </div>
          </div>
        </section>

        <section className="flex items-center px-6 py-10 sm:px-10 lg:px-16">
          <div className="w-full max-w-md mx-auto lg:mx-0">{children}</div>
        </section>
      </main>
    </div>
  );
}
