"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";

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
    () => [
      { id: "DE", label: t("DE") },
      { id: "EN-US", label: t("EN-US") },
      { id: "EN-GB", label: t("EN-GB") },
      { id: "FR", label: t("FR") },
      { id: "ES", label: t("ES") },
      { id: "IT", label: t("IT") },
    ],
    [t],
  );
  const [languages, setLanguages] = useState<Language[]>(defaults);
  const [sourceLang, setSourceLang] = useState<string>("DE");
  const [targetLang, setTargetLang] = useState<string>("EN-US");

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
