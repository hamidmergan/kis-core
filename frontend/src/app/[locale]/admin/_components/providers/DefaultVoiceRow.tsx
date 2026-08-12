"use client";

/**
 * Die Standardstimme, direkt unter der TTS-Route.
 *
 * Sie steht hier und nicht in einer eigenen Karte im KI-Assistenten, weil sie zu den
 * Anbietern gehoert: welche Stimmen es gibt, entscheidet der Anbieter, und der wird
 * genau hier eingerichtet.
 *
 * EIN Feld fuer Anbieter UND Stimme. Text in Sprache ist ein Nutzer-waehlt-Feature,
 * es gibt also gar keinen einen gerouteten Anbieter, an den sich eine Stimme haengen
 * koennte. Ein getrenntes Anbieterfeld waere eine zweite Wahrheit neben der Liste
 * darueber und koennte ihr widersprechen. Deshalb steht in der Liste "Anbieter mal
 * Stimme", und die Wahl schreibt beide Einstellungen in einem Zug.
 *
 * Gebraucht wird sie dort, wo niemand eine Stimme waehlen kann: der Lautsprecher auf
 * einer Lernkarte hat kein Formular. Die Werkzeuge Vertonung und Screencast fragen
 * ihre Nutzer weiterhin selbst.
 */

import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import { SavedMark } from "../../_settings/fields";
import { useSettingGroup } from "../../_settings/SettingsProvider";
import type { Provider } from "./_types";

const ANBIETER = "aia_flashcard_voice_provider_id";
const STIMME = "aia_flashcard_voice_id";
const SCHLUESSEL = [ANBIETER, STIMME];

export default function DefaultVoiceRow({ eligible }: { eligible: Provider[] }) {
  const t = useTranslations("admin.providers.defaultVoice");
  const { settings, loading, save, saving, saved, error } = useSettingGroup(SCHLUESSEL);

  if (loading) return null;

  const anbieter = String(settings?.[ANBIETER] ?? "");
  const stimme = String(settings?.[STIMME] ?? "");
  const wert = anbieter && stimme ? `${anbieter}:${stimme}` : "";

  // Kein Eintrag "Keine" mehr: nichts gewaehlt heisst nicht mehr "kein Lautsprecher",
  // sondern "die erste Stimme der Liste". Ein Ausschalter, der nichts ausschaltet,
  // waere eine Luege im Formular.
  const optionen = eligible.flatMap((p) =>
    (p.voices ?? []).map((v) => ({
      value: `${p.id}:${v.voice_id}`,
      label: `${p.name} · ${v.name}`,
    })),
  );

  // Der gespeicherte Wert steht nicht mehr zur Wahl, etwa weil der Anbieter
  // abgeschaltet oder die Stimme entfernt wurde.
  const verwaist = Boolean(wert && !optionen.some((o) => o.value === wert));

  // Was der Server WIRKLICH benutzt. Ohne Wahl und bei einer verwaisten Wahl faellt
  // er auf die erste Stimme zurueck (siehe aia_flashcard_speech.configured_voice),
  // also zeigt das Feld genau die. Gespeichert wird dabei nichts: ein Schreibvorgang
  // beim blossen Ansehen einer Seite hat hier schon einmal eine Einstellung
  // ueberschrieben.
  const angezeigt = !verwaist && wert ? wert : (optionen[0]?.value ?? "");

  const waehlen = (naechster: string) => {
    // Am ERSTEN Doppelpunkt trennen. Die Anbieternummer ist eine Ziffernfolge, eine
    // Stimmenkennung darf also selbst einen enthalten.
    const i = naechster.indexOf(":");
    const pid = i < 0 ? "" : naechster.slice(0, i);
    const vid = i < 0 ? "" : naechster.slice(i + 1);
    // Beide in EINEM Zug, sonst gibt es einen Augenblick, in dem eine Stimme zu einem
    // Anbieter gespeichert ist, zu dem sie nicht gehoert.
    void save({ [ANBIETER]: pid, [STIMME]: vid });
  };

  return (
    // Nur Beschriftung und Feld, wie die Anbieterzeilen darueber. Ein Erklaertext
    // stand hier und ist wieder weg: die Zeile erklaert sich, und der Kasten wurde
    // doppelt so hoch wie alles andere in der Liste.
    <div className="mt-3 pt-3 border-t border-border-soft">
      <div className="flex items-center gap-2">
        <span className="flex-1 min-w-0 truncate text-sm text-foreground-soft">{t("label")}</span>
        <SavedMark show={saved} />
        <div className="w-64">
          <Select
            value={angezeigt}
            onChange={waehlen}
            options={optionen}
            disabled={saving || optionen.length === 0}
          />
        </div>
      </div>
      {/* Nur Fehlerzustaende, keine Erklaerung. Beide sind selten und beide wuerden
          sonst stillschweigend danebengehen. */}
      {verwaist && <p className="text-2xs text-muted-soft mt-1.5">{t("orphaned")}</p>}
      {error && <p className="text-2xs text-error mt-1.5">{error}</p>}
    </div>
  );
}
