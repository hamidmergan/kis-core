"use client";

/** QR code for an access code: scanning it opens the redeem page with the code already filled in. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import QRCode from "qrcode";

type Props = {
  code: string;
};

export default function AccessCodeQr({ code }: Props) {
  const t = useTranslations("admin.accessCodeQr");
  const [dataUrl, setDataUrl] = useState<string | null>(null);
  const ziel = typeof window === "undefined" ? "" : `${window.location.origin}/redeem?code=${code}`;

  useEffect(() => {
    let aktiv = true;
    QRCode.toDataURL(ziel, { width: 240, margin: 1 })
      .then((url) => { if (aktiv) setDataUrl(url); })
      .catch(() => { if (aktiv) setDataUrl(null); });
    return () => { aktiv = false; };
  }, [ziel]);

  if (!dataUrl) return null;

  return (
    <div className="flex flex-col items-center gap-2 py-2">
      {/* eslint-disable-next-line @next/next/no-img-element -- a data: URL, next/image cannot optimize it */}
      <img src={dataUrl} alt={t("alt")} width={180} height={180} className="rounded-md border border-border" />
      <p className="text-xs text-muted-soft break-all text-center">{ziel}</p>
      <a
        href={dataUrl}
        download={`zugangscode-${code}.png`}
        className="px-3 py-1.5 text-xs border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
      >
        {t("download")}
      </a>
    </div>
  );
}
