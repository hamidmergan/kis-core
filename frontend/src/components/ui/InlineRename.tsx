"use client";

import { useEffect, useRef, useState } from "react";

import { renameCommit, renameErrorText } from "./renameCommit";

/** Field for renaming in place, a rejected name keeps it open. */
export function InlineRename({
  value, onSave, onCancel, errorText,
}: {
  value: string;
  onSave: (next: string) => Promise<void>;
  onCancel: () => void;
  errorText: string;
}) {
  const [entwurf, setEntwurf] = useState(value);
  const [fehler, setFehler] = useState<string | null>(null);
  const [laeuft, setLaeuft] = useState(false);
  const feldRef = useRef<HTMLInputElement>(null);
  // Prevents the second save when Enter leaves the field and triggers blur.
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
        onChange={(e) => { setEntwurf(e.target.value); setFehler(null); }}
        onBlur={() => { void speichern(); }}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); void speichern(); }
          if (e.key === "Escape") { e.preventDefault(); fertigRef.current = true; onCancel(); }
        }}
        className="w-full text-sm font-semibold rounded-md px-2 py-1 bg-background outline-none border-2"
        style={{ borderColor: fehler ? "var(--error-border)" : "var(--kb)", color: "var(--foreground)" }}
      />
      {/* Error line in the style already used for renaming a source. */}
      {fehler && (
        <p className="text-xs mt-1 rounded-md px-2 py-1"
          style={{ backgroundColor: "var(--error-bg)", border: "1px solid var(--error-border)", color: "var(--error-strong)" }}>
          {fehler}
        </p>
      )}
    </div>
  );
}
