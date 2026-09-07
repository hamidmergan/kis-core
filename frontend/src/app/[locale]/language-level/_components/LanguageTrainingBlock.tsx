"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import Spinner from "@/components/ui/Spinner";
import { useNavTransition } from "@/components/ui/useNavTransition";
import { type CefrLevel } from "@/lib/cefr";
import { LevelLadder } from "./LevelLadder";
import { LevelMedallion } from "./LevelMedallion";
import { LevelPicker } from "./LevelPicker";

export interface ProfileMe {
  id: number;
  language_level: CefrLevel | null;
  language_level_set_at: string | null;
  language_level_source: "test" | "self" | null;
  language_training_enabled: boolean;
  language_training_active: boolean;
  language_training_asked_at: string | null;
}

/** The level, where it came from, and the two ways to set it: the test or by hand. */
export function LanguageTrainingBlock({ me, onChanged }: { me: ProfileMe; onChanged: () => void }) {
  const t = useTranslations("languageLevel.languageTraining");
  const locale = useLocale();
  const router = useRouter();
  const [picking, setPicking] = useState(false);
  const [preview, setPreview] = useState<CefrLevel | null>(null);
  const [busy, setBusy] = useState(false);
  const { pending: toTestPending, navigate } = useNavTransition();

  const own = me.language_level;
  const toTest = () => navigate(() => router.push("/language-level/test"));

  const closePicker = () => {
    setPicking(false);
    setPreview(null);
  };

  const applyLevel = async () => {
    if (busy || !preview) return;
    setBusy(true);
    try {
      const res = await fetch("/api/me/language-level", {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level: preview }),
      });
      if (res.ok) {
        closePicker();
        onChanged();
      }
    } catch {
      // A network error stays silent, the level just stays as it was.
    } finally {
      setBusy(false);
    }
  };

  const setAt = me.language_level_set_at
    ? new Date(me.language_level_set_at).toLocaleDateString(locale === "en" ? "en-GB" : "de-DE")
    : null;
  const sourceLine =
    own && setAt
      ? me.language_level_source === "self"
        ? t("sourceSelf", { date: setAt })
        : me.language_level_source === "test"
          ? t("sourceTest", { date: setAt })
          : t("levelSince", { date: setAt })
      : null;

  return (
    <section className="flex flex-col items-center gap-8 py-10 text-center">
      <LevelMedallion level={picking ? (preview ?? own) : own} sourceLine={picking ? null : sourceLine} />
      {picking ? (
        <LevelPicker
          own={own}
          selected={preview ?? own}
          busy={busy}
          onSelect={setPreview}
          onApply={() => void applyLevel()}
          onCancel={closePicker}
          onTest={toTest}
        />
      ) : own ? (
        <>
          <LevelLadder own={own} />
          <button
            type="button"
            onClick={() => setPicking(true)}
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg"
          >
            {t("change")}
          </button>
        </>
      ) : (
        <div className="flex items-center gap-3">
          <button type="button" onClick={toTest} disabled={toTestPending}
            className="px-4 py-2 text-sm btn-primary rounded-lg inline-flex items-center gap-2 disabled:opacity-50">
            {toTestPending && <Spinner size="sm" color="current" />}
            {t("takeTest")}
          </button>
          <button
            type="button"
            onClick={() => setPicking(true)}
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg"
          >
            {t("chooseSelf")}
          </button>
        </div>
      )}
    </section>
  );
}
