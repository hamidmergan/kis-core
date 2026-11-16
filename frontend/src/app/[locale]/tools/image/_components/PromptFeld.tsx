"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { backendApi, parseDetail } from "@/lib/api";
import { FELD, KNOPF } from "../_utils";

export interface PromptEntwurf {
  prompt: string;
  ausformuliert: string;
  formuliert: boolean;
  setPrompt: (text: string) => void;
  setAusformuliert: (text: string) => void;
  ausformulieren: () => Promise<void>;
}

/** The prompt and its worded-out version, shared by the field on the right and the button on the left. */
export function usePromptEntwurf(onFehler: (text: string) => void): PromptEntwurf {
  const tCommon = useTranslations("common");
  const [prompt, setPromptRoh] = useState("");
  const [ausformuliert, setAusformuliert] = useState("");
  const [formuliert, setFormuliert] = useState(false);

  // A changed prompt makes the old worded-out version stale.
  const setPrompt = useCallback((text: string) => { setPromptRoh(text); setAusformuliert(""); }, []);

  const ausformulieren = useCallback(async () => {
    if (!prompt.trim()) return;
    setFormuliert(true);
    onFehler("");
    try {
      const formular = new FormData();
      formular.append("prompt", prompt);
      const antwort = await backendApi.fetch("/image/enhance-prompt", { method: "POST", body: formular });
      const daten = await antwort.json().catch(() => ({}));
      if (!antwort.ok) throw new Error(parseDetail(daten.detail, tCommon("unknownError")));
      setAusformuliert(daten.prompt ?? "");
    } catch (err) {
      onFehler(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      setFormuliert(false);
    }
  }, [prompt, onFehler, tCommon]);

  return { prompt, ausformuliert, formuliert, setPrompt, setAusformuliert, ausformulieren };
}

/** The prompt field with its worded-out version, it stands where the new picture will appear. */
export default function PromptFeld({ entwurf }: { entwurf: PromptEntwurf }) {
  const t = useTranslations("tools.image.generate");
  const { prompt, ausformuliert, formuliert, setPrompt, setAusformuliert, ausformulieren } = entwurf;

  return (
    <>
      <label htmlFor="bild-prompt" className="block text-sm font-medium text-foreground-soft mb-1.5">{t("promptLabel")}</label>
      <textarea
        id="bild-prompt"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={6}
        placeholder={t("promptPlaceholder")}
        className={`${FELD} mb-2`}
      />
      <button type="button" onClick={() => void ausformulieren()} disabled={!prompt.trim() || formuliert}
        className={`${KNOPF} disabled:opacity-50 disabled:cursor-not-allowed`}>
        {formuliert ? t("enhancing") : t("enhance")}
      </button>
      {ausformuliert && (
        <div className="mt-3">
          <label htmlFor="bild-ausformuliert" className="block text-sm font-medium text-foreground-soft mb-1">
            {t("enhancedLabel")}
          </label>
          <textarea id="bild-ausformuliert" value={ausformuliert} onChange={(e) => setAusformuliert(e.target.value)}
            rows={6} className={FELD} />
          <p className="mt-1 text-xs text-muted">{t("enhancedHint")}</p>
        </div>
      )}
    </>
  );
}
