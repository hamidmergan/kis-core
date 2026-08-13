"use client";

import { useEffect, useRef, useState } from "react";

import { renameCommit, renameErrorText } from "./renameCommit";

/**
 * Ein Feld zum Umbenennen, an Ort und Stelle.
 *
 * Abgeschaut vom Umbenennen einer Quelle in `SourceRow.tsx`. Eigene Komponente,
 * weil sonst drei Listen denselben Zustand dreimal halten.
 *
 * Enter und Verlassen des Feldes speichern, Escape verwirft. Was dabei
 * ueberhaupt zu tun ist, entscheidet `renameCommit` nebenan. Ein abgelehnter
 * Name haelt das Feld offen, damit er gleich zu bessern ist.
 */
export function InlineRename({
  value, onSave, onCancel, placeholder, errorText,
}: {
  value: string;
  onSave: (next: string) => Promise<void>;
  onCancel: () => void;
  placeholder?: string;
  errorText: string;
}) {
  const [entwurf, setEntwurf] = useState(value);
  const [fehler, setFehler] = useState<string | null>(null);
  const [laeuft, setLaeuft] = useState(false);
  const feldRef = useRef<HTMLInputElement>(null);
  // Verhindert das zweite Speichern, wenn Enter das Feld verlaesst und dabei blur ausloest.
  const fertigRef = useRef(false);

  useEffect(() => {
    feldRef.current?.select();
  }, []);

  async function speichern() {
    if (laeuft || fertigRef.current) return;
    const was = renameCommit(entwurf, value);
    if (was.kind === "abort") {
      fertigRef.current = true;
      onCancel();
      return;
    }
    setLaeuft(true);
    try {
      await onSave(was.title);
      fertigRef.current = true;
      onCancel();
    } catch (e) {
      setFehler(renameErrorText(e, errorText));
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <div className="flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
      <input
        ref={feldRef}
        type="text"
        value={entwurf}
        disabled={laeuft}
        autoFocus
        placeholder={placeholder}
        onChange={(e) => { setEntwurf(e.target.value); setFehler(null); }}
        onBlur={() => { void speichern(); }}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); void speichern(); }
          if (e.key === "Escape") { e.preventDefault(); fertigRef.current = true; onCancel(); }
        }}
        className="w-full text-sm font-semibold rounded-md px-2 py-1 bg-background outline-none border-2"
        style={{ borderColor: fehler ? "var(--error-border)" : "var(--kb)", color: "var(--foreground)" }}
      />
      {/* Fehlerzeile in der Optik, die das Umbenennen einer Quelle schon benutzt. */}
      {fehler && (
        <p className="text-xs mt-1 rounded-md px-2 py-1"
          style={{ backgroundColor: "var(--error-bg)", border: "1px solid var(--error-border)", color: "var(--error-strong)" }}>
          {fehler}
        </p>
      )}
    </div>
  );
}
