"use client";

/** The public access-code page, a stranger redeems a code to get their own account. */

import { Suspense, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import AuthSplit from "@/components/layout/AuthSplit";
import { Link } from "@/i18n/navigation";
import Spinner from "@/components/ui/Spinner";
import { checkAuthStatus } from "@/lib/auth";
import { AccessCodeDone, AccessCodeForm, useAccessCode } from "./_accessCode";

export default function AccessCodePage() {
  return (
    <Suspense>
      <AccessCodePageInner />
    </Suspense>
  );
}

function AccessCodePageInner() {
  const t = useTranslations("accessCode");
  const searchParams = useSearchParams();

  // A QR code links here with the code already filled in.
  const codeAusLink = useRef(searchParams.get("code") ?? "").current;
  // A plain link only fills in the field, redeeming stays the person's own click.
  const vorbelegt = useRef(searchParams.get("vorbelegt") ?? "").current;
  const state = useAccessCode(codeAusLink || vorbelegt);
  const { error, fertig, redeem } = state;

  // Scanning the QR code (or a shared link) with the code already in the URL needs no click at all.
  const bereitsAusgeloest = useRef(false);
  useEffect(() => {
    if (codeAusLink && !bereitsAusgeloest.current) {
      // React Strict Mode runs effects twice in dev, this must still redeem only once.
      bereitsAusgeloest.current = true;
      checkAuthStatus().then((s) => (s.authenticated ? window.location.assign("/workspace") : redeem(codeAusLink)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A link with the code already tries the redeem right away, no form ever shows for it,
  // only a failed attempt (wrong/expired code) falls back to the normal form with the error.
  const autoLoeseEin = !!codeAusLink && !fertig && !error;

  return (
    <AuthSplit heading={t("welcome")}>
      <h2 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">
        {fertig ? t("doneTitle") : t("title")}
      </h2>

      {fertig ? (
        <AccessCodeDone fertig={fertig} />
      ) : autoLoeseEin ? (
        <div data-testid="access-code-auto" className="mt-6 flex items-center gap-3">
          <Spinner size="lg" />
          <p className="text-sm text-foreground-soft">{t("autoRedeeming")}</p>
        </div>
      ) : (
        <AccessCodeForm state={state} />
      )}

      <Link href="/login" className="mt-6 inline-block text-sm text-kb-dark hover:underline">
        {t("toLogin")}
      </Link>
    </AuthSplit>
  );
}
