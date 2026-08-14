"use client";

/**
 * Bausatz für Einstellungskarten.
 *
 * Vorher hatte jede Karte ihre eigenen achtzig Zeilen aus Laden, Entwurf,
 * Speichern, Fehler und Schalter-Markup. Zwölf Karten, zwölf Kopien, jede
 * minimal anders. Hier steht das einmal.
 *
 * Festgelegtes Verhalten, überall gleich:
 *
 * - Kein Speichern-Knopf. Zahlen und Texte greifen beim Verlassen des Feldes
 *   oder mit Enter, Schalter sofort. Ein Knopf über allen Einstellungen wäre
 *   die andere saubere Möglichkeit, scheitert aber daran, dass die Hälfte der
 *   Einstellungen Schalter sind, und ein Schalter, der erst nach Klick auf
 *   Speichern wirkt, wirkt kaputt.
 * - Sichtbare Rückmeldung. Genau das fehlte vorher: man tippte eine Zahl,
 *   klickte weg und erfuhr nie, ob sie angekommen ist.
 */

import { useEffect, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import type { SettingHandle } from "./SettingsProvider";

/* ------------------------------------------------------------------ */
/* Rahmen                                                              */
/* ------------------------------------------------------------------ */

export function SettingCard({
  title,
  description,
  control,
  error,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  /** Steuerelement rechts oben. Für breite Inhalte stattdessen children nutzen. */
  control?: ReactNode;
  error?: string | null;
  children?: ReactNode;
}) {
  const t = useTranslations("admin");
  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      {/* Umbrechen statt abschneiden: bei 110 % auf einem schmalen Telefon
          bleiben keine 390 px uebrig, und ein Zahlenfeld mit Einheit und
          Tokenzahl passt dann nicht mehr neben den Titel. */}
      <div className="flex items-start justify-between gap-x-4 gap-y-3 flex-wrap">
        <div className="min-w-0 flex-1 basis-64">
          <p className="text-sm font-medium text-foreground">{title}</p>
          {description && <p className="text-xs text-muted mt-1 max-w-2xl">{description}</p>}
        </div>
        {control && (
          <div className="flex items-center gap-3 flex-wrap ml-auto">{control}</div>
        )}
      </div>
      {children}
      {error && (
        <p className="text-xs text-error mt-2">
          {error === "save-failed" ? t("saveFailed") : error}
        </p>
      )}
    </div>
  );
}

/* Hier stand eine Marke "Gespeichert." neben jedem Feld. Sie ist weg: dass eine
   Einstellung sofort greift, weiss man, und ein Schild dafuer ist Laerm. Fehler
   meldet die Karte weiterhin. */

/* ------------------------------------------------------------------ */
/* Schalter                                                            */
/* ------------------------------------------------------------------ */

export function Switch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent
        transition-colors duration-200 focus:outline-none enabled:hover:border-kb
        disabled:opacity-50 ${checked ? "bg-kb" : "bg-border"}`}
    >
      <span
        className={`pointer-events-none inline-block w-5 h-5 bg-white rounded-full shadow
          transition-transform duration-200 ${checked ? "translate-x-5" : "translate-x-0"}`}
      />
    </button>
  );
}

export function ToggleSetting({
  field,
  title,
  activeText,
  disabledText,
  hint,
  label,
}: {
  field: SettingHandle<boolean>;
  title: ReactNode;
  /** Statuszeile bei an, wie bisher in den Karten. */
  activeText: string;
  disabledText: string;
  hint?: ReactNode;
  label: string;
}) {
  if (field.loading) return null;
  const on = field.value ?? false;
  return (
    <SettingCard
      title={title}
      description={on ? activeText : disabledText}
      error={field.error}
      control={
        <Switch checked={on} onChange={(n) => void field.set(n)} disabled={field.saving} label={label} />
      }
    >
      {hint && <p className="mt-3 text-xs text-muted-soft max-w-2xl">{hint}</p>}
    </SettingCard>
  );
}

/* ------------------------------------------------------------------ */
/* Zahl                                                                */
/* ------------------------------------------------------------------ */

export function NumberSetting({
  field,
  title,
  hint,
  unit,
  min,
  max,
  outOfRange,
  suffix,
}: {
  field: SettingHandle<number>;
  title: ReactNode;
  hint?: ReactNode;
  unit?: string;
  min: number;
  max: number;
  /** Meldung bei Werten ausserhalb der Grenzen, aus den Übersetzungen. */
  outOfRange: string;
  /** Zusatz rechts, etwa die ungefähre Tokenzahl. */
  suffix?: (value: number) => ReactNode;
}) {
  const [draft, setDraft] = useState("");
  const [local, setLocal] = useState<string | null>(null);

  // Entwurf nachziehen, wenn der Wert von aussen kommt oder sich ändert.
  useEffect(() => {
    if (field.value !== null) setDraft(String(field.value));
  }, [field.value]);

  if (field.loading || field.value === null) return null;

  const commit = () => {
    const parsed = Number.parseInt(draft, 10);
    if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
      setLocal(outOfRange);
      setDraft(String(field.value));
      return;
    }
    setLocal(null);
    if (parsed !== field.value) void field.set(parsed);
  };

  return (
    <SettingCard
      title={title}
      error={local ?? field.error}
      control={
        <>
          <input
            type="number"
            min={min}
            max={max}
            value={draft}
            onChange={(e) => { setDraft(e.target.value); setLocal(null); }}
            onBlur={commit}
            onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
            disabled={field.saving}
            aria-label={typeof title === "string" ? title : undefined}
            className="w-28 rounded-lg border border-border bg-background px-3 py-1.5 text-sm
              text-foreground text-right tabular-nums focus:outline-none focus:border-kb disabled:opacity-50"
          />
          {unit && <span className="text-xs text-muted-soft whitespace-nowrap">{unit}</span>}
          {suffix?.(field.value)}
        </>
      }
    >
      {hint && <p className="mt-3 text-xs text-muted-soft max-w-2xl">{hint}</p>}
    </SettingCard>
  );
}


/* Ein Baustein "eine Auswahl je Karte" stand hier kurz und ist wieder weg. Die
   einzige Auswahl im Admin-Bereich sind Anbieter und Stimme der Aussprache, und die
   gehoeren in EINE Karte, nicht in zwei. Wer spaeter eine einzelne Auswahl braucht,
   baut sie wie NumberSetting oben, das ist ein Dutzend Zeilen. */
