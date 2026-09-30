"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";

const UPLOAD = "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-8-8v12m0-12l-4 4m4-4l4 4";
const BILD = "M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z";

/** The large picture while nothing is chosen, it says what to do and, for editing and describing, takes an upload. */
export default function Platzhalter({ text, onHochladen, disabled }: {
  text: string;
  onHochladen?: (datei: File) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("tools.image");
  const eingabe = useRef<HTMLInputElement>(null);
  const [drueber, setDrueber] = useState(false);

  const inhalt = (
    <>
      <svg className="mx-auto h-8 w-8 text-muted-soft" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={onHochladen ? UPLOAD : BILD} />
      </svg>
      <p className="mt-3 text-sm text-foreground-soft">{text}</p>
      {onHochladen && (
        <>
          <p className="mt-1 text-sm text-foreground-soft">
            {t.rich("placeholder.upload", { link: (teil) => <span className="font-medium text-kb">{teil}</span> })}
          </p>
          <p className="mt-1 text-xs text-muted">{t("uploadZone.constraints")}</p>
        </>
      )}
    </>
  );

  if (!onHochladen) {
    return (
      <div className="flex aspect-video flex-col items-center justify-center rounded-md border-2 border-dashed border-border bg-background px-6 text-center">
        {inhalt}
      </div>
    );
  }
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => eingabe.current?.click()}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); eingabe.current?.click(); } }}
      onDragOver={(e) => { e.preventDefault(); setDrueber(true); }}
      onDragLeave={(e) => { e.preventDefault(); setDrueber(false); }}
      onDrop={(e) => {
        e.preventDefault();
        setDrueber(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onHochladen(f);
      }}
      className={`flex aspect-video cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed bg-background px-6 text-center transition-colors focus:outline-none ${
        drueber ? "border-kb bg-kb/5" : "border-border hover:border-kb focus:border-kb"
      } ${disabled ? "pointer-events-none opacity-50" : ""}`}
    >
      <input ref={eingabe} type="file" accept=".png,.jpg,.jpeg" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onHochladen(f); e.target.value = ""; }} />
      {inhalt}
    </div>
  );
}
