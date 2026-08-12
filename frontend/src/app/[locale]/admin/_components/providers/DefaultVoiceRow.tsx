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

  const optionen = [
    { value: "", label: t("none") },
    ...eligible.flatMap((p) =>
      (p.voices ?? []).map((v) => ({
        value: `${p.id}:${v.voice_id}`,
        label: `${p.name} · ${v.name}`,
      })),
    ),
  ];

  // Der gespeicherte Wert steht nicht mehr zur Wahl, etwa weil der Anbieter
  // abgeschaltet oder die Stimme entfernt wurde. Das Auswahlfeld zeigt dann nur den
  // allgemeinen Platzhalter, ununterscheidbar von "nichts gewaehlt", deshalb sagt es
  // die Zeile darunter.
  const verwaist = Boolean(wert && !optionen.some((o) => o.value === wert));

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
    <div className="mt-3 pt-3 border-t border-border-soft">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="min-w-0 flex-1 basis-48">
          <p className="text-sm text-foreground-soft">{t("label")}</p>
          <p className="text-2xs text-muted-soft mt-0.5 max-w-xl">{t("hint")}</p>
        </div>
        <SavedMark show={saved} />
        <div className="w-64">
          <Select
            value={verwaist ? "" : wert}
            onChange={waehlen}
            options={optionen}
            disabled={saving}
          />
        </div>
      </div>
      {verwaist && <p className="text-2xs text-muted-soft mt-1.5">{t("orphaned")}</p>}
      {error && <p className="text-2xs text-error mt-1.5">{error}</p>}
    </div>
  );
}
