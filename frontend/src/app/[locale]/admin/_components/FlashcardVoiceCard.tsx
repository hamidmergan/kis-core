"use client";

/**
 * Wer den Beispielsatz einer Lernkarte vorliest.
 *
 * Zwei Auswahlfelder statt einem, weil ein Anbieterwechsel die Stimmenliste
 * austauscht. Beide leer bedeutet: kein Lautsprecher auf der Karte. Das Modell
 * wird hier NICHT gewählt, es kommt aus der Route "Text in Sprache".
 *
 * Beim Anbieterwechsel wird die Stimme geleert, um verwaiste Stimmen zu vermeiden.
 * Gescheiterte Ladevorgänge sind klar von leeren Listen unterschieden: beim Fehler
 * bleiben beide Felder gesperrt, statt eine funktionierende alte Einstellung zu
 * überschreiben.
 */

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useSetting } from "../_settings/SettingsProvider";
import { SelectSetting } from "../_settings/fields";

interface VoiceEntry { voice_id: string; name: string }
interface ProviderEntry { id: number; name: string; voices?: VoiceEntry[] }

type LoadState = "loading" | "error" | "loaded-empty" | "loaded";

export default function FlashcardVoiceCard() {
  const t = useTranslations("admin.flashcardVoiceCard");
  const providerField = useSetting<string>("aia_flashcard_voice_provider_id", "");
  const voiceField = useSetting<string>("aia_flashcard_voice_id", "");
  const [providers, setProviders] = useState<ProviderEntry[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const prevProviderRef = useRef<string>("");

  // Lade Anbieter und Stimmen beim Mount
  useEffect(() => {
    fetch("/api/tts/providers-with-voices", { credentials: "include" })
      .then((r) => {
        // Prüfe auf Serverfehler, bevor der JSON-Body ausgewertet wird.
        // FastAPI liefert auch bei 500-Errors gültiges JSON, z.B. {"detail": ...}.
        // Ohne r.ok-Prüfung würde d.providers undefined sein und wir würden fälschlich
        // in den Zustand "geladen, keine Anbieter" fallen statt in den Fehler.
        if (!r.ok) {
          setLoadState("error");
          return;
        }
        return r.json();
      })
      .then((d) => {
        if (d === undefined) return; // Fehler wurde bereits gehandelt
        const p = d.providers ?? [];
        setProviders(p);
        setLoadState(p.length === 0 ? "loaded-empty" : "loaded");
      })
      .catch(() => setLoadState("error"));
  }, []);

  // Wenn der Anbieter wechselt, leere die Stimme, um verwaiste Werte zu vermeiden.
  useEffect(() => {
    if (providerField.value === null) return;
    const changed =
      providerField.value !== prevProviderRef.current &&
      prevProviderRef.current !== "";
    if (changed && voiceField.value !== "") {
      void voiceField.set("");
    }
    prevProviderRef.current = providerField.value;
  }, [providerField.value]);

  const chosen = providers.find((p) => String(p.id) === providerField.value);

  // Prüfe, ob eine gespeicherte Stimme im gewählten Anbieter nicht existiert.
  const hasOrphanedVoice =
    providerField.value !== "" &&
    voiceField.value !== "" &&
    chosen &&
    !chosen.voices?.some((v) => v.voice_id === voiceField.value);

  const providerOptions = [
    { value: "", label: t("noneOption") },
    ...providers.map((p) => ({ value: String(p.id), label: p.name })),
  ];

  const voiceOptions = [
    { value: "", label: t("noneOption") },
    ...(chosen?.voices ?? []).map((v) => ({ value: v.voice_id, label: v.name })),
  ];

  // Bestimme den Hinweis für das Anbieter-Feld
  let providerHint: string;
  if (loadState === "error") {
    providerHint = t("loadError");
  } else if (loadState === "loaded-empty") {
    providerHint = t("noProviders");
  } else {
    providerHint = t("providerHint");
  }

  // Bestimme den Hinweis für das Stimmen-Feld
  const voiceHint = hasOrphanedVoice ? t("orphanedVoice") : t("voiceHint");

  const isLoaded = loadState === "loaded" || loadState === "loaded-empty";
  const isDisabled = !isLoaded;

  return (
    <>
      <SelectSetting
        field={providerField}
        title={t("providerTitle")}
        hint={providerHint}
        options={providerOptions}
        disabled={isDisabled}
      />
      <SelectSetting
        field={voiceField}
        title={t("voiceTitle")}
        hint={voiceHint}
        options={voiceOptions}
        disabled={isDisabled || !chosen}
      />
    </>
  );
}
