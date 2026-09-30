"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import Checkbox from "@/components/ui/Checkbox";

// The points of the notice, in the order they are read.
const POINTS = ["offer", "dataLeaves", "ownAccount", "noLiability", "clones", "keyStorage"] as const;

/** The notice every person accepts once, before anything on the page can be used. */
export function ConsentNotice({ onAccept }: { onAccept?: () => Promise<void> }) {
  const t = useTranslations("interfaces.consent");
  const [read, setRead] = useState(false);
  const [busy, setBusy] = useState(false);

  const accept = async () => {
    if (!onAccept || !read || busy) return;
    setBusy(true);
    try {
      await onAccept();
    } finally {
      setBusy(false);
    }
  };

  return (
    <section data-testid="interfaces-consent" className="space-y-3">
      <h3 className="text-base font-semibold">{t("title")}</h3>
      <ul className="list-disc pl-5 space-y-2 text-sm" style={{ color: "var(--foreground-soft)" }}>
        {POINTS.map((p) => (
          <li key={p}>{t(`points.${p}`)}</li>
        ))}
      </ul>
      {onAccept && (
        <div className="pt-2 space-y-3">
          <Checkbox
            checked={read}
            onChange={setRead}
            label={t("checkbox")}
            labelClassName="whitespace-normal! text-sm text-foreground text-left"
            className="items-start!"
          />
          <button
            type="button"
            data-testid="interfaces-consent-accept"
            onClick={() => void accept()}
            disabled={!read || busy}
            className="px-4 py-2 text-sm font-medium rounded-md btn-primary disabled:opacity-50"
          >
            {t("accept")}
          </button>
        </div>
      )}
    </section>
  );
}
