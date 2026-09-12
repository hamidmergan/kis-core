"use client";

import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import Tabs from "@/components/ui/Tabs";
import type { ProviderWithVoices } from "@/hooks/useVoices";
import { LANGUAGE_FLAG } from "@/lib/languageFlags";
import StepFooter from "../_components/StepFooter";
import { FIELD } from "./ContentStep";
import { ROLES, type Length, type Person, type PersonCount, type Role, type Style } from "../_types";

const COUNTS = ["1", "2", "3", "4"] as const;
type CountKey = (typeof COUNTS)[number];
const LENGTHS: readonly Length[] = ["short", "medium", "long"];
const STYLES: readonly Style[] = ["teaching", "casual", "interview"];

interface CastStepProps {
  count: PersonCount;
  persons: Person[];
  length: Length;
  style: Style;
  voices: ProviderWithVoices[];
  voicesLoaded: boolean;
  onCount: (count: PersonCount) => void;
  onPerson: (index: number, person: Partial<Person>) => void;
  onLength: (length: Length) => void;
  onStyle: (style: Style) => void;
  onBack: (() => void) | null;
  onNext: () => void;
  /** With a podcast already written this is a recast, not a start. */
  hatAuftrag: boolean;
  busy: boolean;
  error: string;
}

export default function CastStep(props: CastStepProps) {
  const { count, persons, length, style, voices, voicesLoaded, onCount, onPerson, onLength, onStyle,
          onBack, onNext, hatAuftrag, busy, error } = props;
  const t = useTranslations("tools.podcast.cast");
  const voiceOptions = voices.flatMap((p) =>
    p.voices.map((v) => ({
      value: v.voice_id,
      label: `${LANGUAGE_FLAG[v.language] ?? ""} ${v.name}${v.description ? `, ${v.description}` : ""}`.trim(),
    })),
  );
  // A voice only works together with the provider it belongs to.
  const anbieterVon = new Map(voices.flatMap((p) => p.voices.map((v) => [v.voice_id, p.id])));
  const active = persons.slice(0, count);
  const keineStimmen = voicesLoaded && voiceOptions.length === 0;
  const complete = active.every((p) => p.name.trim().length > 0 && p.voiceId && p.providerId > 0) && !keineStimmen;

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-4">{t("heading")}</h2>

      {hatAuftrag && <p className="mb-6 text-sm text-muted">{t("recastHint")}</p>}

      <div className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2" role="group" aria-label={t("countAria")}>
        <Tabs<CountKey>
          variant="pill"
          active={String(count) as CountKey}
          onChange={(key) => onCount(Number(key) as PersonCount)}
          items={COUNTS.map((key) => ({ key, label: key }))}
        />
        <p className="text-sm text-muted">{t(`countHint.${count}`)}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 mb-2">
        {active.map((person, i) => (
          <div key={i} className="border-2 border-border-soft rounded-xl bg-background p-4">
            <p className="text-sm font-medium text-foreground mb-3">{t("personTitle", { n: i + 1 })}</p>
            <div className="space-y-3">
              <div>
                <label htmlFor={`podcast-name-${i}`} className="block text-xs font-medium text-foreground-soft mb-1">
                  {t("nameLabel")}
                </label>
                <input id={`podcast-name-${i}`} type="text" value={person.name} onChange={(e) => onPerson(i, { name: e.target.value })} className={FIELD} />
              </div>
              <div>
                <label htmlFor={`podcast-role-${i}`} className="block text-xs font-medium text-foreground-soft mb-1">
                  {t("roleLabel")}
                </label>
                <Select<Role>
                  id={`podcast-role-${i}`}
                  value={person.role}
                  onChange={(role) => onPerson(i, { role })}
                  options={ROLES.map((role) => ({ value: role, label: t(`roles.${role}`) }))}
                />
              </div>
              <div>
                <label htmlFor={`podcast-voice-${i}`} className="block text-xs font-medium text-foreground-soft mb-1">
                  {t("voiceLabel")}
                </label>
                <Select
                  id={`podcast-voice-${i}`}
                  value={person.voiceId}
                  onChange={(voiceId) => onPerson(i, { voiceId, providerId: anbieterVon.get(voiceId) ?? 0 })}
                  options={voiceOptions}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
      <a href="/tools/tts/voices" target="_blank" rel="noopener noreferrer" className="text-sm text-kb hover:underline">
        {t("previewVoices")}
      </a>

      <div className="grid gap-4 sm:grid-cols-2 mt-6">
        <div>
          <label htmlFor="podcast-length" className="block text-sm font-medium text-foreground-soft mb-2">
            {t("lengthLabel")}
          </label>
          <Select<Length> id="podcast-length" value={length} onChange={onLength} disabled={hatAuftrag} options={LENGTHS.map((l) => ({ value: l, label: t(`lengths.${l}`) }))} />
        </div>
        <div>
          <label htmlFor="podcast-style" className="block text-sm font-medium text-foreground-soft mb-2">
            {t("styleLabel")}
          </label>
          <Select<Style> id="podcast-style" value={style} onChange={onStyle} disabled={hatAuftrag} options={STYLES.map((s) => ({ value: s, label: t(`styles.${s}`) }))} />
        </div>
      </div>

      {hatAuftrag && <p className="mt-2 text-xs text-muted-soft">{t("writtenHint")}</p>}

      {error && (
        <p className="mt-6 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="alert">
          {error}
        </p>
      )}

      {keineStimmen && (
        <p className="mt-6 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="alert">
          {t("noVoices")}
        </p>
      )}

      <StepFooter
        onBack={onBack}
        nextLabel={hatAuftrag ? t("nextRecast") : t("next")}
        onNext={onNext}
        nextDisabled={!complete || busy}
      />
    </section>
  );
}
