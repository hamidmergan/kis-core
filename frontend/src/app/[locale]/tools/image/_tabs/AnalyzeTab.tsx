"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import Spinner from "@/components/ui/Spinner";
import BackgroundHint from "@/components/tools/BackgroundHint";
import ProviderSelect from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import UploadZone from "../_components/UploadZone";
import { validateImageFile } from "../_utils";


export default function AnalyzeTab() {
  const t = useTranslations("tools.image.analyze");
  const tImage = useTranslations("tools.image");
  const tCommon = useTranslations("common");
  const { providers, providerId, setProviderId } = useFeatureProviders("/image/providers/analyze");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [spinnerLabel, setSpinnerLabel] = useState(t("spinner"));
  const [error, setError] = useState("");
  const [resultText, setResultText] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) { setPreviewUrl(null); return; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleFileSelect = useCallback((f: File) => {
    const err = validateImageFile(f, tCommon);
    if (err) { setError(err); return; }
    setError("");
    setFile(f);
    setResultText(null);
  }, [tCommon]);

  const handleSubmit = useCallback(async () => {
    if (!file) return;
    setLoading(true);
    setSpinnerLabel(t("spinner"));
    setError("");
    setResultText(null);
    try {
      const formData = new FormData();
      formData.append("image", file);
      formData.append("prompt", prompt);
      if (providerId != null) formData.append("provider_id", String(providerId));
      const response = await backendApi.fetch("/image/analyze", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, tCommon("unknownError")));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setSpinnerLabel(t("longRunning")),
        60_000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
      const { blob } = await downloadJobAsBlob(data.job_uuid);
      const text = await blob.text();
      setResultText(text);
    } catch (err) {
      setError(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      setLoading(false);
    }
  }, [file, prompt, providerId, t, tCommon]);

  return (
    <section>
      <UploadZone
        file={file}
        dragOver={dragOver}
        disabled={loading}
        inputRef={fileRef}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) handleFileSelect(f);
        }}
        onChange={handleFileSelect}
      />

      {previewUrl && (
        <div className="mb-4 rounded-lg overflow-hidden border border-border-soft">
          <img src={previewUrl} alt={tImage("previewAlt")} className="w-full max-h-64 object-contain bg-surface" />
        </div>
      )}

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={3}
        placeholder={t("promptPlaceholder")}
        className="w-full rounded-md border border-border px-3 py-2 text-sm text-foreground placeholder:text-muted-soft focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none mb-4"
      />

      <ProviderSelect
        id="image-analyze-provider"
        label={tImage("providerLabel")}
        providers={providers}
        value={providerId}
        onChange={setProviderId}
        disabled={loading}
      />

      {!resultText && (
        <button
          onClick={handleSubmit}
          disabled={!file || loading}
          className="w-full px-4 py-3 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? tCommon("processing") : t("submit")}
        </button>
      )}

      {loading && <Spinner label={spinnerLabel} className="justify-center mt-6" />}
      {loading && <BackgroundHint />}
      {error && <p className="mt-4 text-sm text-error" role="alert">{error}</p>}
      {resultText && (
        <div className="mt-6">
          <div className="rounded-lg border border-border-soft bg-surface p-4 mb-3">
            <p className="text-sm text-foreground whitespace-pre-wrap">{resultText}</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                const blob = new Blob([resultText], { type: "text/plain" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = file ? file.name.replace(/\.[^.]+$/, "_analyse.txt") : "analyse.txt";
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="px-5 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
            >
              <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              TXT
            </button>
            <button
              onClick={() => setResultText(null)}
              className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface transition-colors"
            >
              {t("regenerate")}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
