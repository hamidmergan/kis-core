"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import UploadZone from "./UploadZone";
import { validateImageFile, type Uebergabe } from "../_utils";

interface Props {
  datei: File | null;
  onDatei: (datei: File) => void;
  onFehler: (text: string) => void;
  uebergabe: Uebergabe | null;
  disabled: boolean;
  label: string;
}

/** The picture to work on: dropped, chosen, or handed over from a result or the history, with a preview. */
export default function BildWahl({ datei, onDatei, onFehler, uebergabe, disabled, label }: Props) {
  const t = useTranslations("tools.image");
  const tCommon = useTranslations("common");
  const [dragOver, setDragOver] = useState(false);
  const [vorschau, setVorschau] = useState<string | null>(null);
  const eingabe = useRef<HTMLInputElement>(null);
  const zuletzt = useRef<number | null>(null);

  // A handed over picture arrives once per hand-over, the id tells a new one from a repeated render.
  useEffect(() => {
    if (uebergabe && uebergabe.id !== zuletzt.current) {
      zuletzt.current = uebergabe.id;
      onDatei(uebergabe.datei);
    }
  }, [uebergabe, onDatei]);

  useEffect(() => {
    if (!datei) { setVorschau(null); return; }
    const url = URL.createObjectURL(datei);
    setVorschau(url);
    return () => URL.revokeObjectURL(url);
  }, [datei]);

  const nimm = (f: File) => {
    const fehler = validateImageFile(f, tCommon);
    if (fehler) { onFehler(fehler); return; }
    onFehler("");
    onDatei(f);
  };

  return (
    <div className="mb-4">
      <p className="text-sm font-medium text-foreground-soft mb-2">{label}</p>
      {vorschau && (
        <img src={vorschau} alt={t("previewAlt")} className="mb-2 max-h-56 w-full rounded-md border border-border-soft object-contain bg-surface" />
      )}
      <UploadZone
        file={datei}
        dragOver={dragOver}
        disabled={disabled}
        inputRef={eingabe}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) nimm(f);
        }}
        onChange={nimm}
      />
    </div>
  );
}
