"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import {
  DEFAULT_TRANSLATE_SOURCE,
  DEFAULT_TRANSLATE_TARGET,
  TRANSLATE_LANGUAGES,
} from "@/lib/constants";

export interface Language {
  id: string;
  label: string;
}

interface TranslateConfigResponse {
  languages: Language[];
  default_source: string;
  default_target: string;
}

export function useLanguageConfig() {
  const t = useTranslations("langLabels");
  const defaults = useMemo<Language[]>(
    () => TRANSLATE_LANGUAGES.map((id) => ({ id, label: t(id) })),
    [t],
  );
  const [languages, setLanguages] = useState<Language[]>(defaults);
  const [sourceLang, setSourceLang] = useState<string>(DEFAULT_TRANSLATE_SOURCE);
  const [targetLang, setTargetLang] = useState<string>(DEFAULT_TRANSLATE_TARGET);

  useEffect(() => {
    api
      .getJson<TranslateConfigResponse>("/api/translate/config")
      .then((data) => {
        if (data.languages?.length) setLanguages(data.languages);
        if (data.default_source) setSourceLang(data.default_source);
        if (data.default_target) setTargetLang(data.default_target);
      })
      .catch(() => {});
  }, []);

  return { languages, sourceLang, setSourceLang, targetLang, setTargetLang };
}
