"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { CalendarBlank } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ScheduleMonth from "@/components/schedule/ScheduleMonth";

export default function SchedulePage() {
  const t = useTranslations("schedule");

  return (
    <ProtectedRoute>
      {/* Fester Rand statt der prozentualen page-shell: ein Monatsraster braucht
          die Breite, prozentual bleiben auf 1400 px ueber 200 px ungenutzt. */}
      <div className="px-4 sm:px-6 lg:px-8 2xl:px-12 pt-10 pb-20 lg:pt-15 lg:pb-30">
        <h1 className="text-xl font-bold flex items-center gap-2 mb-6" style={{ color: "var(--foreground)" }}>
          <CalendarBlank size={20} weight="bold" style={{ color: "var(--kb)" }} />
          {t("title")}
        </h1>

        {/* The query string is only readable inside a Suspense boundary. */}
        <Suspense fallback={null}>
          <MonthFromQuery />
        </Suspense>
      </div>
    </ProtectedRoute>
  );
}

/** A day from the start page calendar opens right here. */
function MonthFromQuery() {
  const date = useSearchParams().get("date");
  return <ScheduleMonth key={date ?? ""} initialDate={date ?? undefined} />;
}
