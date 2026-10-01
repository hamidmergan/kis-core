"use client";

import { useCallback, useEffect, useState } from "react";
import type { MascotVariant } from "@/components/ui/Mascot";
import { PREFS_KEY, readPrefs, updatePrefs } from "@/lib/browserStore";

const CHANGE_EVENT = "ki-assistent-mascot-pref:change";

// Francis is the default character for everyone who has not picked one.
const DEFAULT_VARIANT: MascotVariant = "francis";

// Francis is the only character on offer, every other stored value lands on him.
function isVariant(v: unknown): v is MascotVariant {
  return v === "francis";
}

function readLocalVariant(): MascotVariant {
  // Everything else, old values included, lands on the default character.
  const raw = readPrefs().mascot;
  return isVariant(raw) ? raw : DEFAULT_VARIANT;
}

export interface MascotPref {
  /** Which character to render. A mascot is always shown. */
  variant: MascotVariant;
  setVariant: (variant: MascotVariant) => void;
}

export function useMascotPref(): MascotPref {
  const [variant, setVariantState] = useState<MascotVariant>(DEFAULT_VARIANT);

  useEffect(() => {
    setVariantState(readLocalVariant());

    const onCustom = (e: Event) => {
      const detail = (e as CustomEvent<MascotVariant>).detail;
      if (isVariant(detail)) setVariantState(detail);
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === PREFS_KEY) setVariantState(readLocalVariant());
    };

    window.addEventListener(CHANGE_EVENT, onCustom);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(CHANGE_EVENT, onCustom);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  // Side effects belong in the handler, in the updater they would run during render.
  const setVariant = useCallback((next: MascotVariant) => {
    setVariantState(next);
    updatePrefs({ mascot: next });
    try { window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: next })); } catch { /* ignore */ }
  }, []);

  return { variant, setVariant };
}
