"use client";

import { useCallback, useEffect, useState } from "react";
import type { MascotVariant } from "@/components/ui/Mascot";

const STORAGE_KEY = "ki-assistent-mascot";
const CHANGE_EVENT = "ki-assistent-mascot-pref:change";

// Francis is the default character for everyone who has not picked one.
const DEFAULT_VARIANT: MascotVariant = "francis";

function isVariant(v: unknown): v is MascotVariant {
  return v === "hilde" || v === "francis";
}

function readLocalVariant(): MascotVariant {
  if (typeof window === "undefined") return DEFAULT_VARIANT;
  try {
    // Anything else, including the retired "off" choice and the even older
    // on/off toggle, lands on the default character.
    const raw = localStorage.getItem(STORAGE_KEY);
    return isVariant(raw) ? raw : DEFAULT_VARIANT;
  } catch {
    return DEFAULT_VARIANT;
  }
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
      if (e.key === STORAGE_KEY) setVariantState(readLocalVariant());
    };

    window.addEventListener(CHANGE_EVENT, onCustom);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(CHANGE_EVENT, onCustom);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  // Side effects run in the event handler, not inside the setState updater — an
  // updater runs during render, where dispatching would trigger setState in
  // other listeners mid-render (React's "Cannot update a component while
  // rendering a different component" warning).
  const setVariant = useCallback((next: MascotVariant) => {
    setVariantState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* ignore */ }
    try { window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: next })); } catch { /* ignore */ }
  }, []);

  return { variant, setVariant };
}
