"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface Language {
  id: string;
  label: string;
}

const DEFAULT_LANGUAGES: Language[] = [
  { id: "DE", label: "Deutsch" },
  { id: "EN-US", label: "Englisch" },
  { id: "EN-GB", label: "Englisch (UK)" },
  { id: "FR", label: "Französisch" },
  { id: "ES", label: "Spanisch" },
  { id: "IT", label: "Italienisch" },
];

interface TranslateConfigResponse {
  languages: Language[];
  default_source: string;
  default_target: string;
}

export function useLanguageConfig() {
  const [languages, setLanguages] = useState<Language[]>(DEFAULT_LANGUAGES);
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
