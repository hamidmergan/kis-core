"use client";

/** The default voice, one of the starred provider's voices. */

import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import { useSettingGroup } from "../../_settings/SettingsProvider";
import { defaultVoiceOptions, shownDefaultVoice } from "./_defaultVoice";
import type { Provider } from "./_types";

const ANBIETER = "aia_flashcard_voice_provider_id";
const STIMME = "aia_flashcard_voice_id";
const SCHLUESSEL = [ANBIETER, STIMME];

export default function DefaultVoiceRow({ eligible, starId }: { eligible: Provider[]; starId: number | null }) {
  const t = useTranslations("admin.providers.defaultVoice");
  const { settings, loading, save, saving, error } = useSettingGroup(SCHLUESSEL);

  if (loading) return null;

  const anbieter = String(settings?.[ANBIETER] ?? "");
  const stimme = String(settings?.[STIMME] ?? "");
  const wert = anbieter && stimme ? `${anbieter}:${stimme}` : "";

  // No 'none' entry any more, nothing chosen means the first voice.
  const optionen = defaultVoiceOptions(eligible, starId);

  // The field shows what the server really uses, nothing is saved.
  const { shown: angezeigt, orphaned: verwaist } = shownDefaultVoice(optionen, wert, starId);

  const waehlen = (naechster: string) => {
    // Split at the first colon, the voice id may carry one itself.
    const i = naechster.indexOf(":");
    const pid = i < 0 ? "" : naechster.slice(0, i);
    const vid = i < 0 ? "" : naechster.slice(i + 1);
    // Both in one go, otherwise voice and provider briefly do not match.
    void save({ [ANBIETER]: pid, [STIMME]: vid });
  };

  return (
    // Only a label and a field, flush with the model fields of the provider rows above.
    <div className="mt-3 pt-3 border-t border-border-soft">
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-2">
        <span className="sm:flex-1 min-w-0 truncate text-sm text-foreground-soft">{t("label")}</span>
        <div className="sm:flex-1 min-w-0 flex items-center gap-2">
          <div className="flex-1 min-w-0">
            <Select
              value={angezeigt}
              onChange={waehlen}
              options={optionen}
              disabled={saving || optionen.length === 0}
            />
          </div>
          <span className="w-18 shrink-0" aria-hidden="true" />
        </div>
      </div>
      {/* Nur Fehlerzustaende, keine Erklaerung. Beide sind selten und beide wuerden
          sonst stillschweigend danebengehen. */}
      {verwaist && <p className="text-2xs text-muted-soft mt-1.5">{t("orphaned")}</p>}
      {error && <p className="text-2xs text-error mt-1.5">{error}</p>}
    </div>
  );
}
