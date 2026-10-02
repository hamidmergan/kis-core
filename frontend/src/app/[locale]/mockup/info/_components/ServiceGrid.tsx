"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { ArrowRight, CheckCircle } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import { TOOL_ICONS } from "@/lib/toolIcons";
import type { ToolKey } from "@/lib/modules";
import Band from "./Band";
import { SectionHeading } from "./InfoSections";
import Screenshot from "./Screenshot";

const SERVICES: ToolKey[] = [
  "translation",
  "tts",
  "transcription",
  "summary",
  "podcast",
  "praesentation",
  "screencast",
  "image",
  "glossary",
];

const POINTS = ["p1", "p2", "p3"] as const;

/** Description and screenshot of one service, opened from its card. */
function ServiceDetail({ service, onClose }: { service: ToolKey | null; onClose: () => void }) {
  const t = useTranslations("mockup.info.services");
  const tools = useTranslations("startOverview.tools");
  if (!service) return null;
  const Icon = TOOL_ICONS[service];
  // The page is zoomed on wide screens, a fixed dialog inside it would be scaled and shifted, so it goes to the body.
  return createPortal(
    <Modal
      open
      onClose={onClose}
      size="xl"
      title={
        <span className="flex items-center gap-3">
          <span className="flex items-center justify-center w-9 h-9 shrink-0 rounded-full bg-kb text-on-accent">
            <Icon size={20} weight="bold" aria-hidden="true" />
          </span>
          <span className="text-lg font-semibold tracking-[-0.01em]">{tools(`${service}.title`)}</span>
        </span>
      }
    >
      <div className="flex flex-col gap-6 py-1" data-testid="service-detail">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-10">
          <p className="text-lg leading-snug text-foreground-soft">{t(`detail.${service}.lead`)}</p>
          <ul className="flex flex-col gap-3">
            {POINTS.map((point) => (
              <li key={point} className="flex items-start gap-3">
                <CheckCircle size={22} weight="bold" className="shrink-0 mt-0.5 text-kb-dark" aria-hidden="true" />
                <span className="text-base leading-snug text-foreground">{t(`detail.${service}.${point}`)}</span>
              </li>
            ))}
          </ul>
        </div>
        <Screenshot name={`svc-${service}`} alt={t(`detail.${service}.alt`)} />
      </div>
    </Modal>,
    document.body,
  );
}

/** The services teachers find on the start page, each card opens a description with a screenshot. */
export default function ServiceGrid() {
  const t = useTranslations("mockup.info.services");
  const tools = useTranslations("startOverview.tools");
  const [open, setOpen] = useState<ToolKey | null>(null);
  return (
    <Band testId="info-services">
      <div className="flex flex-col gap-8">
        <div className="max-w-3xl flex flex-col gap-2">
          <SectionHeading>{t("heading")}</SectionHeading>
          <p className="text-lg @min-[40rem]:text-xl leading-snug text-foreground-soft">{t("intro")}</p>
        </div>
        <ul className="grid grid-cols-1 @min-[40rem]:grid-cols-2 @min-[64rem]:grid-cols-3 gap-4 @min-[40rem]:gap-6">
          {SERVICES.map((key) => {
            const Icon = TOOL_ICONS[key];
            return (
              <li key={key} data-testid="service-item">
                <button
                  type="button"
                  onClick={() => setOpen(key)}
                  aria-haspopup="dialog"
                  className="flex h-full w-full flex-col items-start gap-3 rounded-2xl border-2 border-border-soft bg-background p-6 text-left transition-colors hover:border-kb"
                >
                  <span className="flex items-center justify-center w-12 h-12 rounded-full bg-kb text-on-accent">
                    <Icon size={24} weight="bold" aria-hidden="true" />
                  </span>
                  <span className="text-lg font-semibold tracking-[-0.01em] text-foreground">{tools(`${key}.title`)}</span>
                  <span className="flex-1 text-base leading-snug text-foreground-soft">{tools(`${key}.body`)}</span>
                  <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-kb-dark">
                    {t("more")}
                    <ArrowRight size={16} weight="bold" aria-hidden="true" />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      <ServiceDetail service={open} onClose={() => setOpen(null)} />
    </Band>
  );
}
