"use client";

import { useTranslations } from "next-intl";
import { CaretDown, ChatCircleText } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { FAQ_GRUPPEN } from "./_katalog";

/** Questions sorted by problem, while the manual is sorted by feature. Open to everyone with a session. */
export default function FaqPage() {
  const t = useTranslations("faq");
  const rowClass =
    "flex items-start gap-3 px-4 py-3 text-sm font-medium cursor-pointer list-none " +
    "hover:bg-[var(--surface-dim)] focus-visible:bg-[var(--surface-dim)] outline-none " +
    "[&::-webkit-details-marker]:hidden group-open:text-kb-dark";

  return (
    <ProtectedRoute>
      <div className="page-shell pt-10 pb-20 lg:pt-15 lg:pb-30">
        <div className="max-w-3xl mx-auto flex flex-col gap-8">
          <header className="flex flex-col gap-2">
            <h1 className="text-xl font-bold flex items-center gap-2" style={{ color: "var(--foreground)" }}>
              <ChatCircleText size={20} weight="bold" style={{ color: "var(--kb)" }} />
              {t("title")}
            </h1>
            <p className="text-sm text-foreground-soft">{t("intro")}</p>
          </header>

          {FAQ_GRUPPEN.map((gruppe) => (
            <section key={gruppe.key} className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
                {t(`groups.${gruppe.key}`)}
              </h2>
              <div className="rounded-xl border border-border-soft bg-background overflow-hidden">
                {gruppe.items.map((schluessel, i) => (
                  <details
                    key={schluessel}
                    className={`group${i > 0 ? " border-t border-border-soft" : ""}`}
                  >
                    <summary className={rowClass}>
                      <CaretDown
                        size={14}
                        weight="bold"
                        className="shrink-0 mt-1 text-muted transition-transform group-open:rotate-180"
                        aria-hidden="true"
                      />
                      <span>{t(`items.${schluessel}.q`)}</span>
                    </summary>
                    <div className="flex flex-col gap-3 px-4 pb-4 pl-11 text-sm text-foreground-soft">
                      {t.has(`items.${schluessel}.a`) && (
                        <p className="whitespace-pre-line">{t(`items.${schluessel}.a`)}</p>
                      )}
                      {t.has(`items.${schluessel}.todo`) && (
                        <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-lg border border-dashed border-border bg-surface px-3 py-2.5 text-muted">
                          <span className="text-3xs font-bold uppercase tracking-wider text-muted-soft">
                            {t("todoLabel")}
                          </span>
                          {t(`items.${schluessel}.todo`)}
                        </p>
                      )}
                    </div>
                  </details>
                ))}
              </div>
            </section>
          ))}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-info-border bg-info-bg px-4 py-3.5 text-sm text-foreground-soft">
            <b className="font-semibold" style={{ color: "var(--foreground)" }}>
              {t("closer.heading")}
            </b>
            <span>
              {t.rich("closer.body", {
                manual: (chunks) => (
                  <Link href="/manual" className="font-medium underline underline-offset-2 text-info-strong">
                    {chunks}
                  </Link>
                ),
                feedback: (chunks) => (
                  <Link href="/feedback" className="font-medium underline underline-offset-2 text-info-strong">
                    {chunks}
                  </Link>
                ),
              })}
            </span>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
