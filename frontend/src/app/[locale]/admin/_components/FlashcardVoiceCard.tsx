"use client";

/**
 * Wer den Beispielsatz einer Lernkarte vorliest.
 *
 * Zwei Auswahlfelder statt einem, weil ein Anbieterwechsel die Stimmenliste
 * austauscht. Beide leer bedeutet: kein Lautsprecher auf der Karte. Das Modell
 * wird hier NICHT gewählt, es kommt aus der Route "Text in Sprache".
 */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useSetting } from "../_settings/SettingsProvider";
import { SelectSetting } from "../_settings/fields";

interface VoiceEntry { voice_id: string; name: string }
interface ProviderEntry { id: number; name: string; voices?: VoiceEntry[] }

export default function FlashcardVoiceCard() {
  const t = useTranslations("admin.flashcardVoiceCard");
  const providerField = useSetting<string>("aia_flashcard_voice_provider_id", "");
  const voiceField = useSetting<string>("aia_flashcard_voice_id", "");
  const [providers, setProviders] = useState<ProviderEntry[] | null>(null);

  useEffect(() => {
    fetch("/api/tts/providers-with-voices", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setProviders(d.providers ?? []))
      .catch(() => setProviders([]));
  }, []);

  const chosen = providers?.find((p) => String(p.id) === providerField.value);
  const providerOptions = [
    { value: "", label: t("noneOption") },
    ...(providers ?? []).map((p) => ({ value: String(p.id), label: p.name })),
  ];
  const voiceOptions = [
    { value: "", label: t("noneOption") },
    ...(chosen?.voices ?? []).map((v) => ({ value: v.voice_id, label: v.name })),
  ];

  return (
    <>
      <SelectSetting
        field={providerField}
        title={t("providerTitle")}
        hint={providers?.length === 0 ? t("noProviders") : t("providerHint")}
        options={providerOptions}
        disabled={providers === null}
      />
      <SelectSetting
        field={voiceField}
        title={t("voiceTitle")}
        hint={t("voiceHint")}
        options={voiceOptions}
        disabled={providers === null || !chosen}
      />
    </>
  );
}
