"use client";

import { useTranslations } from "next-intl";
import { CaretDown } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { FAQ_GRUPPEN } from "./_katalog";

/** Questions sorted by problem, while the manual is sorted by feature. Open to everyone with a session. */
export default function FaqPage() {
  const t = useTranslations("faq");
  const rowClass =
    "row-expandable flex items-baseline gap-4 py-3.5 text-[0.9375rem] cursor-pointer " +
    "list-none [&::-webkit-details-marker]:hidden";

  return (
    <ProtectedRoute>
      <div className="px-4 sm:px-6 lg:px-8 pt-10 pb-20 lg:pt-15 lg:pb-30">
        <div className="max-w-3xl mx-auto flex flex-col gap-8">
          <header className="flex flex-col gap-2">
            <h1 className="text-xl font-bold" style={{ color: "var(--foreground)" }}>
              {t("title")}
            </h1>
            <p className="text-sm text-foreground-soft">{t("intro")}</p>
          </header>

          <div className="faq-list">
            {FAQ_GRUPPEN.map((gruppe) => (
              <section key={gruppe.key} className="faq-group">
                <h2 className="faq-label">{t(`groups.${gruppe.key}`)}</h2>
                <div>
                  {gruppe.items.map((schluessel) => (
                    <details key={schluessel} name="faq" className="faq-item group">
                      <summary className={rowClass}>
                        <span className="faq-q">{t(`items.${schluessel}.q`)}</span>
                        <span className="row-caret shrink-0 transition-colors" aria-hidden="true">
                          <CaretDown
                            size={14}
                            weight="bold"
                            className="transition-transform group-open:rotate-180"
                          />
                        </span>
                      </summary>
                      <div className="flex flex-col gap-3 pb-4 text-sm leading-relaxed text-foreground-soft max-w-[62ch]">
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
          </div>

          <div
            className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg px-4 py-3 text-sm"
            style={{ backgroundColor: "var(--info-bg)", color: "var(--foreground)" }}
          >
            <strong className="font-semibold">{t("closer.heading")}</strong>
            <span>
              {t.rich("closer.body", {
                manual: (chunks) => (
                  <Link href="/manual" className="underline" style={{ color: "var(--kb-dark)" }}>
                    {chunks}
                  </Link>
                ),
                feedback: (chunks) => (
                  <Link href="/feedback" className="underline" style={{ color: "var(--kb-dark)" }}>
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
