"use client";

import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import Modal from "@/components/ui/Modal";
import { uploadVorlage } from "../_api";
import type { Vorlage } from "../_types";

export const FIELD =
  "w-full px-3 py-2 text-sm border border-border rounded-md bg-background hover:border-kb focus:outline-none focus:border-kb placeholder:text-muted-soft";

const STIL_BEISPIEL =
  "Editorial illustration in a limited palette: bright vermilion red, black ink, pure white background. No text, no letters, no logos.";

interface VorlageHochladenProps {
  onClose: () => void;
  onUploaded: (v: Vorlage) => void;
}

/** Upload of an own template with name and picture style, the file goes into the same drop area the material uses. */
export default function VorlageHochladen({ onClose, onUploaded }: VorlageHochladenProps) {
  const t = useTranslations("tools.praesentation.upload");
  const tCommon = useTranslations("common");
  const tCancel = useTranslations("tools.praesentation.common");
  const [datei, setDatei] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [stil, setStil] = useState("");
  const [fehler, setFehler] = useState("");
  const [laeuft, setLaeuft] = useState(false);
  const [ueberZone, setUeberZone] = useState(false);
  const dateiRef = useRef<HTMLInputElement>(null);

  const nimm = (f: File | null) => {
    if (!f) return;
    setDatei(f);
    if (!name) setName(f.name.replace(/\.[^.]+$/, ""));
  };

  const senden = async () => {
    if (!datei) return;
    setLaeuft(true);
    setFehler("");
    try {
      onUploaded(await uploadVorlage(datei, name, stil));
    } catch (e) {
      setFehler(e instanceof Error && e.message ? e.message : tCommon("unknownError"));
    } finally {
      setLaeuft(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={t("title")}
      size="md"
      footer={
        <>
          <button type="button" onClick={onClose} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
            {tCancel("cancel")}
          </button>
          <button type="button" onClick={senden} disabled={!datei || laeuft} className="px-4 py-2 text-sm btn-primary rounded-lg">
            {t("submit")}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <div
            role="button"
            tabIndex={0}
            aria-label={t("fileAria")}
            onDragOver={(e) => {
              e.preventDefault();
              setUeberZone(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setUeberZone(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              setUeberZone(false);
              nimm(e.dataTransfer.files?.[0] ?? null);
            }}
            onClick={() => dateiRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                dateiRef.current?.click();
              }
            }}
            className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 transition-colors cursor-pointer ${
              ueberZone ? "border-kb bg-kb/5" : datei ? "border-kb" : "border-border hover:border-kb"
            }`}
          >
            <input
              ref={dateiRef}
              type="file"
              accept=".pptx,.potx"
              className="hidden"
              aria-label={t("fileAria")}
              onChange={(e) => {
                nimm(e.target.files?.[0] ?? null);
                e.target.value = "";
              }}
            />
            <svg className="w-8 h-8 text-muted-soft mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-sm text-foreground-soft text-center break-all">
              {datei ? datei.name : <>{t("dropOrBrowse")} <span className="text-kb font-medium">{t("browse")}</span></>}
            </p>
          </div>
          <p className="text-xs text-muted mt-1">{t("rulesHint")}</p>
        </div>
        <label className="block text-sm">
          <span className="font-medium">{t("nameLabel")}</span>
          <input className={`${FIELD} mt-1`} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
        </label>
        <label className="block text-sm">
          <span className="font-medium">{t("styleLabel")}</span>
          <textarea className={`${FIELD} mt-1 resize-y`} rows={3} value={stil} placeholder={STIL_BEISPIEL}
                    onChange={(e) => setStil(e.target.value)} maxLength={1000} />
          <span className="text-xs text-muted">{t("styleHint")}</span>
        </label>
        {fehler && <p className="text-sm text-error">{fehler}</p>}
      </div>
    </Modal>
  );
}
