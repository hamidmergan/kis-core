"use client";

import { useEffect, useState } from "react";
import { api, backendApi } from "@/lib/api";
import type { LangCode, LanguageOption, ProviderOption } from "../_types";

const LANG_CODES: readonly string[] = ["DE", "EN-US"];
const FALLBACK_PROVIDERS: ProviderOption[] = [{ id: -1, label: "THL myLab" }];

/** Languages and providers from the platform, with a stand-in so the choice is always visible. */
export function useInterpreterConfig(fallbackLanguages: LanguageOption[]) {
  const [languages, setLanguages] = useState<LanguageOption[]>(fallbackLanguages);
  const [translationProviders, setTranslationProviders] = useState<ProviderOption[]>(FALLBACK_PROVIDERS);
  const [sttProviders, setSttProviders] = useState<ProviderOption[]>(FALLBACK_PROVIDERS);

  useEffect(() => {
    let active = true;
    api
      .fetch("/translate/config")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { providers?: ProviderOption[]; languages?: { id: string; label: string }[] } | null) => {
        if (!active || !data) return;
        const langs = (data.languages ?? []).filter((l) => LANG_CODES.includes(l.id)) as LanguageOption[];
        if (langs.length === 2) setLanguages(langs);
        if (data.providers?.length) setTranslationProviders(data.providers);
      })
      .catch(() => {});
    backendApi
      .fetch("/transcription/providers")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { providers?: { id: number; name: string }[]; default_id?: number | null } | null) => {
        if (!active || !data?.providers?.length) return;
        // The admin default comes first, the page picks the first entry.
        const list = data.providers.map((p) => ({ id: p.id, label: p.name }));
        list.sort((a, b) => Number(b.id === data.default_id) - Number(a.id === data.default_id));
        setSttProviders(list);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const labelOf = (code: LangCode) => languages.find((l) => l.id === code)?.label ?? code;

  return { languages, translationProviders, sttProviders, labelOf };
}
