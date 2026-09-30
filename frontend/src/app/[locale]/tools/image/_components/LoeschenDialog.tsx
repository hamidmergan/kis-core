"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";

/** Asks once before a picture and its job are gone for good, the same dialog as for a slide. */
export default function LoeschenDialog({ name, loescht, fehler, onAbbrechen, onLoeschen }: {
  name: string;
  loescht: boolean;
  fehler: string;
  onAbbrechen: () => void;
  onLoeschen: () => void;
}) {
  const t = useTranslations("tools.image.deleteDialog");
  return (
    <Modal open onClose={onAbbrechen} size="sm" title={t("title")}
      footer={<>
        <button type="button" onClick={onAbbrechen} disabled={loescht}
          className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg disabled:opacity-50">{t("cancel")}</button>
        <button type="button" onClick={onLoeschen} disabled={loescht}
          className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50">{loescht ? "..." : t("confirm")}</button>
      </>}>
      <p className="text-sm font-medium break-words">{name}</p>
      <p className="text-sm text-muted mt-2">{t("warning")}</p>
      {fehler && <p className="text-sm text-error mt-2" role="alert">{fehler}</p>}
    </Modal>
  );
}
