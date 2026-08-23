"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import {
  DEFAULT_TRANSLATE_TARGET,
  TRANSLATE_LANGUAGES,
} from "@/lib/constants";
import { pickAllowed } from "./_language_config";

export interface Language {
  id: string;
  label: string;
}

interface TranslateConfigResponse {
  languages: Language[];
  default_target: string;
}

export function useLanguageConfig(allowed?: readonly string[]) {
  const t = useTranslations("langLabels");
  const defaults = useMemo<Language[]>(
    () => TRANSLATE_LANGUAGES.map((id) => ({ id, label: t(id) })),
    [t],
  );
  const [languages, setLanguages] = useState<Language[]>(defaults);
  const [targetLang, setTargetLang] = useState<string>(DEFAULT_TRANSLATE_TARGET);

  useEffect(() => {
    api
      .getJson<TranslateConfigResponse>("/api/translate/config")
      .then((data) => {
        if (data.languages?.length) setLanguages(data.languages);
        if (data.default_target) setTargetLang(data.default_target);
      })
      .catch(() => {});
  }, []);

  const erlaubt = useMemo(
    () => pickAllowed(languages, allowed, targetLang),
    [languages, allowed, targetLang],
  );

  return {
    languages: erlaubt.languages,
    targetLang: erlaubt.target,
    setTargetLang,
  };
}
