"use client";

/**
 * Einstellungen einmal laden, überall benutzen.
 *
 * Vorher stand in SettingsTab.tsx zwanzigmal `fetch("/api/admin/settings")`.
 * Jede Karte holte sich die vollständigen Einstellungen selbst, eine Seite mit
 * fünf Karten machte also fünf gleiche Anfragen. Dazu sechs handgeschriebene
 * Speicher-Funktionen und ein Dutzend Ladezustände, jeder leicht anders.
 *
 * Hier gibt es eine Anfrage pro Seite und einen Weg zu speichern. Damit ist
 * auch das Verhalten an einer Stelle festgelegt statt vierzehnmal: kein
 * Speichern-Knopf, jede Änderung greift sofort und meldet sich kurz zurück.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type Settings = Record<string, unknown>;

interface Ctx {
  settings: Settings | null;
  /** Speichert und schreibt den Wert erst nach Erfolg fest. */
  save: (patch: Settings) => Promise<boolean>;
  /** Schlüssel, die gerade gespeichert werden. */
  pending: Set<string>;
  /** Schlüssel, die eben erfolgreich gespeichert wurden. Läuft von selbst ab. */
  justSaved: Set<string>;
  /** Fehlermeldung je Schlüssel, null wenn alles gut ging. */
  errors: Record<string, string | null>;
  reload: () => void;
}

const SettingsCtx = createContext<Ctx | null>(null);

/** Wie lange die Marke "Gespeichert" stehen bleibt. Lang genug zum Lesen,
 *  kurz genug, um nicht als Dauerzustand missverstanden zu werden. */
const SAVED_MS = 2600;

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [justSaved, setJustSaved] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const load = useCallback(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d: Settings) => setSettings(d))
      .catch(() => setSettings({}));
  }, []);

  useEffect(load, [load]);

  // Beim Verlassen der Seite laufende Marken abräumen, sonst setzt ein
  // abgelaufener Zeitgeber Zustand auf einer nicht mehr sichtbaren Karte.
  useEffect(() => {
    const map = timers.current;
    return () => { map.forEach(clearTimeout); map.clear(); };
  }, []);

  const save = useCallback(async (patch: Settings) => {
    const keys = Object.keys(patch);
    setPending((p) => new Set([...p, ...keys]));
    setErrors((e) => {
      const next = { ...e };
      keys.forEach((k) => { next[k] = null; });
      return next;
    });
    try {
      const res = await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!res.ok) {
        let detail = "";
        try { detail = (await res.json())?.detail ?? ""; } catch { /* egal */ }
        setErrors((e) => {
          const next = { ...e };
          keys.forEach((k) => { next[k] = detail || "save-failed"; });
          return next;
        });
        return false;
      }
      // Erst nach Erfolg festschreiben. Sonst zeigt die Oberfläche einen Wert,
      // den der Server nie angenommen hat.
      setSettings((s) => ({ ...(s ?? {}), ...patch }));
      setJustSaved((j) => new Set([...j, ...keys]));
      keys.forEach((k) => {
        clearTimeout(timers.current.get(k));
        timers.current.set(
          k,
          setTimeout(() => {
            setJustSaved((j) => { const n = new Set(j); n.delete(k); return n; });
            timers.current.delete(k);
          }, SAVED_MS),
        );
      });
      return true;
    } catch {
      setErrors((e) => {
        const next = { ...e };
        keys.forEach((k) => { next[k] = "save-failed"; });
        return next;
      });
      return false;
    } finally {
      setPending((p) => {
        const n = new Set(p);
        keys.forEach((k) => n.delete(k));
        return n;
      });
    }
  }, []);

  const value = useMemo<Ctx>(
    () => ({ settings, save, pending, justSaved, errors, reload: load }),
    [settings, save, pending, justSaved, errors, load],
  );

  return <SettingsCtx.Provider value={value}>{children}</SettingsCtx.Provider>;
}

function useSettingsCtx(): Ctx {
  const ctx = useContext(SettingsCtx);
  if (!ctx) throw new Error("useSetting braucht einen SettingsProvider darüber.");
  return ctx;
}

export interface SettingHandle<T> {
  /** null solange geladen wird. */
  value: T | null;
  set: (next: T) => Promise<boolean>;
  saving: boolean;
  saved: boolean;
  error: string | null;
  loading: boolean;
}

/**
 * Eine Einstellung lesen und schreiben.
 *
 *   const ocr = useSetting<boolean>("ocr_enabled", false);
 *   <ToggleSetting field={ocr} ... />
 */
export function useSetting<T>(key: string, fallback: T): SettingHandle<T> {
  const { settings, save, pending, justSaved, errors } = useSettingsCtx();
  const loading = settings === null;
  const raw = settings?.[key];

  return {
    value: loading ? null : ((raw ?? fallback) as T),
    set: (next: T) => save({ [key]: next }),
    saving: pending.has(key),
    saved: justSaved.has(key),
    error: errors[key] ?? null,
    loading,
  };
}

/** Mehrere Schlüssel in einem Rutsch, etwa die vier Felder der Workspace-Bezeichnung. */
export function useSettingGroup(keys: string[]) {
  const { settings, save, pending, justSaved, errors } = useSettingsCtx();
  return {
    settings,
    loading: settings === null,
    save,
    saving: keys.some((k) => pending.has(k)),
    saved: keys.some((k) => justSaved.has(k)),
    error: keys.map((k) => errors[k]).find(Boolean) ?? null,
  };
}
