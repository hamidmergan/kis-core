"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { updateVorlage } from "../_api";
import type { Vorlage } from "../_types";
import { FIELD } from "./VorlageHochladen";

interface VorlageBearbeitenProps {
  vorlage: Vorlage;
  onClose: () => void;
  onSaved: (v: Vorlage) => void;
}

/** Rename and restyle an own template, the uploaded file itself stays untouched. */
export default function VorlageBearbeiten({ vorlage, onClose, onSaved }: VorlageBearbeitenProps) {
  const t = useTranslations("tools.praesentation.upload");
  const tCommon = useTranslations("common");
  const tActions = useTranslations("tools.praesentation.common");
  const [name, setName] = useState(vorlage.name);
  const [stil, setStil] = useState(vorlage.stiltext);
  const [fehler, setFehler] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  const senden = async () => {
    setLaeuft(true);
    setFehler("");
    try {
      onSaved(await updateVorlage(vorlage.id, name, stil));
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
      title={t("editTitle")}
      size="md"
      footer={
        <>
          <button type="button" onClick={onClose} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
            {tActions("cancel")}
          </button>
          <button type="button" onClick={senden} disabled={!name.trim() || laeuft} className="px-4 py-2 text-sm btn-primary rounded-lg">
            {tActions("save")}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block text-sm">
          <span className="font-medium">{t("nameLabel")}</span>
          <input className={`${FIELD} mt-1`} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
        </label>
        <label className="block text-sm">
          <span className="font-medium">{t("styleLabel")}</span>
          <textarea className={`${FIELD} mt-1 resize-y`} rows={3} value={stil}
                    onChange={(e) => setStil(e.target.value)} maxLength={1000} />
          <span className="text-xs text-muted">{t("styleHint")}</span>
        </label>
        {fehler && <p className="text-sm text-error">{fehler}</p>}
      </div>
    </Modal>
  );
}
