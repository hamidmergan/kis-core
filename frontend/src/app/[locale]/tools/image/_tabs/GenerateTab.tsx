"use client";

import { useCallback, useState } from "react";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import Spinner from "@/components/ui/Spinner";
import { SIZES, COUNTS } from "../_utils";


export default function GenerateTab() {
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState<string>("1024x1024");
  const [n, setN] = useState(1);
  const [loading, setLoading] = useState(false);
  const [spinnerLabel, setSpinnerLabel] = useState("Wird generiert…");
  const [error, setError] = useState("");
  const [results, setResults] = useState<Array<{ url: string; filename: string }>>([]);
  const [jobUuid, setJobUuid] = useState<string | null>(null);

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setSpinnerLabel("Wird generiert…");
    setError("");
    setResults([]);
    setJobUuid(null);
    try {
      const formData = new FormData();
      formData.append("prompt", prompt);
      formData.append("size", size);
      formData.append("n", String(n));
      const response = await backendApi.fetch("/image/generate", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      const jobStatus = await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setSpinnerLabel("Läuft noch - Bildgenerierung kann etwas länger dauern…"),
        60_000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
      setJobUuid(data.job_uuid);
      const inlined = jobStatus.result as { images?: Array<{ b64_json: string; filename: string }> } | null;
      if (inlined?.images) {
        const mapped = inlined.images.map((img) => {
          const bytes = Uint8Array.from(atob(img.b64_json), (c) => c.charCodeAt(0));
          const imgBlob = new Blob([bytes], { type: "image/png" });
          return { url: URL.createObjectURL(imgBlob), filename: img.filename };
        });
        setResults(mapped);
      } else {
        const { blob, filename } = await downloadJobAsBlob(data.job_uuid);
        setResults([{ url: URL.createObjectURL(blob), filename }]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setLoading(false);
    }
  }, [prompt, size, n]);

  return (
    <section>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={4}
        placeholder="Beschreiben Sie das gewünschte Bild ..."
        className="w-full rounded-md border border-border px-3 py-2 text-sm text-foreground placeholder:text-muted-soft focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none mb-4"
      />

      <div className="mb-4">
        <p className="text-sm font-medium text-foreground-soft mb-2">Größe</p>
        <div className="flex flex-wrap gap-2">
          {SIZES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSize(s)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                size === s
                  ? "border-kb bg-kb/10 text-kb"
                  : "border-border text-foreground-soft hover:bg-surface"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-6">
        <p className="text-sm font-medium text-foreground-soft mb-2">Anzahl</p>
        <div className="flex gap-2">
          {COUNTS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setN(c)}
              className={`w-10 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                n === c
                  ? "border-kb bg-kb/10 text-kb"
                  : "border-border text-foreground-soft hover:bg-surface"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {!results.length && (
        <button
          onClick={handleGenerate}
          disabled={!prompt.trim() || loading}
          className="w-full px-4 py-3 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Wird verarbeitet…" : "Bild generieren"}
        </button>
      )}

      {loading && <Spinner label={spinnerLabel} className="justify-center mt-6" />}
      {error && <p className="mt-4 text-sm text-error" role="alert">{error}</p>}
      {results.length > 0 && (
        <div className="mt-6">
          <div className={`${results.length > 1 ? "grid grid-cols-2 gap-4" : ""}`}>
            {results.map((result, i) => (
              <div key={i}>
                <img
                  src={result.url}
                  alt={`Generiertes Bild ${i + 1}`}
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
              </div>
            ))}
          </div>
          {results.length > 1 && jobUuid && (
            <a
              href={`/api/jobs/${jobUuid}/download`}
              download
              className="mt-4 w-full px-3 py-1.5 btn-primary text-xs font-medium rounded-md  transition-colors flex items-center justify-center gap-2"
            >
              <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Alle als ZIP
            </a>
          )}
          <button
            onClick={() => { setResults([]); setJobUuid(null); }}
            className="mt-4 px-4 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface transition-colors"
          >
            Neu generieren
          </button>
        </div>
      )}
    </section>
  );
}
