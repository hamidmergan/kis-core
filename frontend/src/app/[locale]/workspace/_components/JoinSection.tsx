"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { extractJoinCode } from "./joinInput";

interface JoinSectionProps {
  /** Called once the code checked out and the page is on its way. */
  onDone?: () => void;
  /** Side by side instead of stacked, for the empty list where space is tight. */
  compact?: boolean;
}

/**
 * The field that takes a link or a code and hands over to the enrollment card.
 *
 * Lives apart from any dialog so both places can show it: the dialog behind the
 * join button and the empty list. It only checks whether the code is known, the
 * rest is the existing path behind `?code=`, so a clicked link and a typed code
 * end up in the same place.
 */
export default function JoinSection({ onDone, compact = false }: JoinSectionProps) {
  const t = useTranslations("workspace.list");
  const router = useRouter();
  const [value, setValue] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const code = extractJoinCode(value);
    if (!code) {
      setError(t("joinUnreadable"));
      return;
    }
    setChecking(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/ai-assistant/access-link/preview?code=${encodeURIComponent(code)}`,
        { credentials: "include" },
      );
      if (!res.ok) {
        setError(t("joinUnknown"));
        return;
      }
      // The card on the start page takes over from here.
      router.replace(`/?code=${encodeURIComponent(code)}`);
      onDone?.();
    } catch {
      setError(t("unknownError"));
    } finally {
      setChecking(false);
    }
  }

  const field = (
    <input
      id="join-module-code"
      autoFocus
      value={value}
      onChange={(e) => {
        setValue(e.target.value);
        setError(null);
      }}
      placeholder={compact ? t("joinField") : undefined}
      className="w-full rounded-lg border px-3 py-2 text-sm font-mono focus:outline-none"
      style={{
        backgroundColor: "var(--background)",
        borderColor: error ? "var(--error-border)" : "var(--border)",
        color: "var(--foreground)",
      }}
    />
  );

  const submit = (
    <button
      type="submit"
      data-testid="join-submit"
      disabled={checking || !value.trim()}
      className="btn-primary px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 whitespace-nowrap"
    >
      {checking ? t("joinChecking") : compact ? t("joinButton") : t("joinSubmit")}
    </button>
  );

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 text-left">
      {!compact && (
        <p className="text-sm" style={{ color: "var(--foreground-soft)" }}>
          {t("joinBody")}
        </p>
      )}

      {compact ? (
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0">{field}</div>
          {submit}
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          <label
            htmlFor="join-module-code"
            className="text-sm font-medium"
            style={{ color: "var(--foreground)" }}
          >
            {t("joinField")}
          </label>
          {field}
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            {t("joinHint")}
          </p>
        </div>
      )}

      {error && (
        <p className="text-sm" style={{ color: "var(--error)" }}>
          {error}
        </p>
      )}

      {!compact && <div className="flex justify-end">{submit}</div>}
    </form>
  );
}
