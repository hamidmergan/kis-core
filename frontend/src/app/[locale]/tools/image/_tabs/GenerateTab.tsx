"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import Spinner from "@/components/ui/Spinner";
import ProviderSelect from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { SIZES } from "../_utils";


export default function GenerateTab() {
  const t = useTranslations("tools.image.generate");
  const tImage = useTranslations("tools.image");
  const tCommon = useTranslations("common");
  const { providers, providerId, setProviderId } = useFeatureProviders("/image/providers/generate");
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState<string>("1024x1024");
  const [loading, setLoading] = useState(false);
  const [spinnerLabel, setSpinnerLabel] = useState(t("spinner"));
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ url: string; filename: string } | null>(null);

  // Free the object URL when it is replaced (regenerate) or the tab unmounts.
  // The cleanup closes over the previous url, so each new result revokes the old one.
  useEffect(() => {
    const url = result?.url;
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [result?.url]);

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setSpinnerLabel(t("spinner"));
    setError("");
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("prompt", prompt);
      formData.append("size", size);
      if (providerId != null) formData.append("provider_id", String(providerId));
      const response = await backendApi.fetch("/image/generate", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, `${tCommon("unknownError")}: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setSpinnerLabel(t("longRunning")),
        60_000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
      const { blob, filename } = await downloadJobAsBlob(data.job_uuid);
      setResult({ url: URL.createObjectURL(blob), filename });
    } catch (err) {
      setError(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      setLoading(false);
    }
  }, [prompt, size, providerId, t, tCommon]);

  return (
    <section>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={4}
        placeholder={t("promptPlaceholder")}
        className="w-full rounded-md border border-border px-3 py-2 text-sm text-foreground placeholder:text-muted-soft focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none mb-4"
      />

      <ProviderSelect
        id="image-gen-provider"
        label={tImage("providerLabel")}
        providers={providers}
        value={providerId}
        onChange={setProviderId}
        disabled={loading}
      />

      <div className="mb-6">
        <p className="text-sm font-medium text-foreground-soft mb-2">{t("size")}</p>
        <div className="flex flex-wrap gap-2">
          {SIZES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSize(s)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md border-2 transition-colors ${
                size === s
                  ? "border-kb bg-kb/10 text-kb dark:text-foreground"
                  : "border-border text-foreground-soft hover:border-kb"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {!result && (
        <button
          onClick={handleGenerate}
          disabled={!prompt.trim() || loading}
          className="w-full px-4 py-3 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? tCommon("processing") : t("submit")}
        </button>
      )}

      {loading && <Spinner label={spinnerLabel} className="justify-center mt-6" />}
      {error && <p className="mt-4 text-sm text-error" role="alert">{error}</p>}
      {result && (
        <div className="mt-6">
          <img
            src={result.url}
            alt={t("resultAlt")}
            className="w-full rounded-lg border border-border-soft bg-surface mb-2"
          />
          <button
            onClick={() => {
              const a = document.createElement("a");
              a.href = result.url;
              a.download = result.filename;
              a.click();
            }}
            className="w-full px-3 py-1.5 btn-primary text-xs font-medium rounded-md  transition-colors flex items-center justify-center gap-2"
          >
            <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            PNG
          </button>
          <button
            onClick={() => setResult(null)}
            className="mt-4 px-4 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface transition-colors"
          >
            {t("regenerate")}
          </button>
        </div>
      )}
    </section>
  );
}
