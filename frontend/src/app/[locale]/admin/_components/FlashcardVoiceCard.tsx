"use client";

/**
 * Wer den Beispielsatz einer Lernkarte vorliest.
 *
 * EINE Karte mit zwei Feldern, nicht zwei Karten. Anbieter und Stimme sind eine
 * einzige Entscheidung: eine Stimme ohne Anbieter ergibt nichts, und der Anbieter
 * bestimmt, welche Stimmen überhaupt zur Wahl stehen. Zwei Karten haben das
 * auseinandergerissen und denselben Hinweis zweimal erzählt.
 *
 * Das Modell wird hier NICHT gewählt, es kommt aus der Route "Text in Sprache".
 *
 * Beim Anbieterwechsel wird die Stimme geleert, sonst bliebe eine verwaiste Stimme
 * stehen, die es beim neuen Anbieter nicht gibt. Ein gescheiterter Abruf ist klar
 * vom leeren Ergebnis unterschieden: beim Fehler bleiben beide Felder gesperrt,
 * statt dass ein Klick eine funktionierende Einstellung überschreibt.
 */

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import { useSetting } from "../_settings/SettingsProvider";
import { SavedMark, SettingCard } from "../_settings/fields";

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

  // Anbieter samt Stimmen einmal holen.
  useEffect(() => {
    fetch("/api/tts/providers-with-voices", { credentials: "include" })
      .then((r) => {
        // Erst den Status prüfen, dann den Körper. FastAPI liefert auch bei einem 500
        // gültiges JSON, etwa {"detail": ...}. Ohne diese Prüfung wäre d.providers
        // undefined und wir landeten im Zustand "geladen, keine Anbieter" statt im
        // Fehler, und ein Klick könnte eine funktionierende Einstellung löschen.
        if (!r.ok) {
          setLoadState("error");
          return;
        }
        return r.json();
      })
      .then((d) => {
        if (d === undefined) return; // Fehler ist oben schon behandelt
        const p = d.providers ?? [];
        setProviders(p);
        setLoadState(p.length === 0 ? "loaded-empty" : "loaded");
      })
      .catch(() => setLoadState("error"));
  }, []);

  // Wechselt der Anbieter, fällt die Stimme weg. Sie gehört zum alten Anbieter und
  // gibt es beim neuen in aller Regel nicht.
  useEffect(() => {
    if (providerField.value === null) return;
    const gewechselt =
      providerField.value !== prevProviderRef.current &&
      prevProviderRef.current !== "";
    if (gewechselt && voiceField.value !== "") {
      void voiceField.set("");
    }
    prevProviderRef.current = providerField.value;
  }, [providerField.value]);

  if (providerField.loading || providerField.value === null || voiceField.value === null) {
    return null;
  }

  const chosen = providers.find((p) => String(p.id) === providerField.value);

  // Eine gespeicherte Stimme, die es beim gewählten Anbieter nicht gibt. Das Feld
  // zeigt dann nur den allgemeinen Platzhalter, ununterscheidbar von "nichts gewählt",
  // deshalb sagt es der Hinweis.
  const hasOrphanedVoice = Boolean(
    providerField.value !== "" &&
    voiceField.value !== "" &&
    chosen &&
    !chosen.voices?.some((v) => v.voice_id === voiceField.value),
  );

  const providerOptions = [
    { value: "", label: t("noneOption") },
    ...providers.map((p) => ({ value: String(p.id), label: p.name })),
  ];

  const voiceOptions = [
    { value: "", label: t("noneOption") },
    ...(chosen?.voices ?? []).map((v) => ({ value: v.voice_id, label: v.name })),
  ];

  const isLoaded = loadState === "loaded" || loadState === "loaded-empty";
  const gesperrt = !isLoaded;

  // Genau ein Sonderhinweis, und nur wenn es einen gibt. Die Reihenfolge ist die der
  // Dringlichkeit: ein Ladefehler macht jede Aussage über die Liste hinfällig.
  let notiz: string | null = null;
  if (loadState === "error") notiz = t("loadError");
  else if (loadState === "loaded-empty") notiz = t("noProviders");
  else if (hasOrphanedVoice) notiz = t("orphanedVoice");

  const feld = (
    beschriftung: string,
    field: typeof providerField,
    options: ReadonlyArray<{ value: string; label: string }>,
    disabled: boolean,
    breite: string,
  ) => (
    <div className={breite}>
      <p className="text-2xs font-medium text-muted-soft mb-1">{beschriftung}</p>
      <Select
        value={field.value ?? ""}
        onChange={(next) => void field.set(next)}
        options={options}
        disabled={disabled || field.saving}
      />
    </div>
  );

  return (
    <SettingCard
      title={t("title")}
      error={providerField.error ?? voiceField.error}
      control={
        <>
          <SavedMark show={providerField.saved || voiceField.saved} />
          {feld(t("providerLabel"), providerField, providerOptions, gesperrt, "w-52")}
          {feld(t("voiceLabel"), voiceField, voiceOptions, gesperrt || !chosen, "w-40")}
        </>
      }
    >
      <p className="mt-3 text-xs text-muted-soft max-w-2xl">{t("description")}</p>
      {notiz && <p className="mt-2 text-xs text-muted-soft max-w-2xl">{notiz}</p>}
    </SettingCard>
  );
}
