"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import Select from "@/components/ui/Select";
import GlossarySelector from "@/components/glossary/GlossarySelector";
import type { ProviderOption } from "../_types";

interface Props {
  open: boolean;
  onClose: () => void;
  sttProviders: ProviderOption[];
  sttProviderId: number | null;
  onStt: (id: number) => void;
  translationProviders: ProviderOption[];
  translationProviderId: number | null;
  onTranslation: (id: number) => void;
  glossaryIds: string[];
  onGlossary: (ids: string[]) => void;
}

/** Providers and glossary, behind the gear so the conversation stays clean. */
export default function SettingsModal(p: Props) {
  const t = useTranslations("tools.interpreter.settings");
  const toOptions = (list: ProviderOption[]) => list.map((x) => ({ value: String(x.id), label: x.label }));
  return (
    <Modal
      open={p.open}
      onClose={p.onClose}
      title={t("title")}
      size="md"
      footer={
        <button type="button" onClick={p.onClose} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
          {t("close")}
        </button>
      }
    >
      <p className="text-sm text-muted mb-4">{t("description")}</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="interpreter-stt-provider" className="block text-sm font-medium text-foreground-soft mb-2">
            {t("sttProvider")}
          </label>
          <Select
            id="interpreter-stt-provider"
            value={String(p.sttProviderId ?? "")}
            onChange={(v) => p.onStt(Number(v))}
            options={toOptions(p.sttProviders)}
          />
        </div>
        <div>
          <label htmlFor="interpreter-translation-provider" className="block text-sm font-medium text-foreground-soft mb-2">
            {t("translationProvider")}
          </label>
          <Select
            id="interpreter-translation-provider"
            value={String(p.translationProviderId ?? "")}
            onChange={(v) => p.onTranslation(Number(v))}
            options={toOptions(p.translationProviders)}
          />
        </div>
      </div>
      <GlossarySelector values={p.glossaryIds} onChange={p.onGlossary} />
      <p className="mt-4 text-xs text-muted">{t("privacy")}</p>
    </Modal>
  );
}
