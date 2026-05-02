"use client";

import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";


export function TranslatingStep({ onCancel }: { onCancel: () => void }) {
  const t = useTranslations("tools.screencast");
  const tDemo = useTranslations("tools.screencastDemo");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft animate-pulse">{tDemo("loadingDemo")}</p>
      <p className="text-xs text-muted-soft mt-2">{tDemo("loadingDemoSubtle")}</p>
      <button onClick={onCancel}
        className="btn-cancel mt-6 px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
        {t("common.cancel")}
      </button>
    </section>
  );
}


export function GeneratingScriptsStep({ slideCount, onCancel }: { slideCount: number; onCancel: () => void }) {
  const t = useTranslations("tools.screencast");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft animate-pulse">{t("generatingScripts.title")}</p>
      <p className="text-xs text-muted-soft mt-2">{t("generatingScripts.subtle", { n: slideCount })}</p>
      <button onClick={onCancel}
        className="btn-cancel mt-6 px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
        {t("common.cancel")}
      </button>
    </section>
  );
}


export function RenderingStep({ renderProgressLabel, onCancel }: { renderProgressLabel: string; onCancel: () => void }) {
  const t = useTranslations("tools.screencast");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft">{renderProgressLabel || t("rendering.fallback")}</p>
      {!renderProgressLabel && <p className="text-xs text-muted-soft mt-2">{t("rendering.subtle")}</p>}
      <button onClick={onCancel}
        className="btn-cancel mt-6 px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
        {t("common.cancel")}
      </button>
    </section>
  );
}


export function ErrorStep({ errorMessage, onReset }: { errorMessage: string; onReset: () => void }) {
  const t = useTranslations("tools.screencast");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-12">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full bg-error-bg flex items-center justify-center">
          <svg className="w-6 h-6 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
      </div>
      <h2 className="text-lg font-bold text-error-strong mb-2">{t("error.heading")}</h2>
      {errorMessage && <p className="text-sm text-error mb-3">{errorMessage}</p>}
      <div className="flex gap-3 justify-center">
        <button onClick={onReset} aria-label={t("done.newPresentationAria")}
          className="px-6 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors">
          {t("done.newPresentation")}
        </button>
      </div>
    </section>
  );
}
