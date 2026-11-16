"use client";

/** The test button of a route and the line that tells its result. */

import { useTranslations } from "next-intl";
import { CheckCircle, Lightning, Spinner, Warning, XCircle } from "@phosphor-icons/react";

export type TestState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ok" }
  | { kind: "warning"; message: string }
  | { kind: "error"; message: string };

// Codes the backend answers that have a translated sentence.
const KNOWN_WARNINGS = new Set([
  "stt_model_not_validated_by_provider",
  "stt_endpoint_verified_model_unvalidated",
]);
const KNOWN_ERRORS = new Set([
  "model_name_not_set",
  "tts_speech_endpoint_not_found",
  "endpoint_not_found",
  "auth_rejected",
  "server_error",
  "unreachable",
  "no_voices_configured",
]);

export function resultToState(res: { status: "ok" | "error"; error: string | null; warning?: string | null }): TestState {
  if (res.status === "ok") {
    return res.warning ? { kind: "warning", message: res.warning } : { kind: "ok" };
  }
  return { kind: "error", message: res.error || "unknown error" };
}

export function TestButton({
  state,
  disabled,
  onClick,
}: {
  state: TestState;
  disabled: boolean;
  onClick: () => void;
}) {
  const t = useTranslations("admin.providers");
  const running = state.kind === "running";
  const label = t("routes.test");
  const ok = state.kind === "ok";
  const warn = state.kind === "warning";
  const err = state.kind === "error";
  const tone = ok
    ? "text-success hover:outline hover:outline-2 hover:outline-success"
    : warn
      ? "text-warn hover:outline hover:outline-2 hover:outline-warn"
      : err
        ? "text-error hover:outline hover:outline-2 hover:outline-error"
        : "text-muted hover:text-kb hover:outline hover:outline-2 hover:outline-kb";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || running}
      title={label}
      aria-label={label}
      className={`w-8 h-8 rounded-md border border-border-soft bg-background flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${tone}`}
    >
      {running ? (
        <Spinner size={14} weight="bold" className="animate-spin" />
      ) : ok ? (
        <CheckCircle size={14} weight="bold" />
      ) : warn ? (
        <Warning size={14} weight="bold" />
      ) : err ? (
        <XCircle size={14} weight="bold" />
      ) : (
        <Lightning size={14} weight="bold" />
      )}
    </button>
  );
}

export function TestStatusLine({ state }: { state: TestState }) {
  const t = useTranslations("admin.providers");
  if (state.kind === "ok") {
    return <p className="text-2xs text-success mt-1">{t("routes.testOk")}</p>;
  }
  if (state.kind === "warning") {
    const msg = KNOWN_WARNINGS.has(state.message)
      ? t(`routes.testErrors.${state.message}` as Parameters<typeof t>[0])
      : state.message;
    return <p className="text-2xs text-warn mt-1">{msg}</p>;
  }
  if (state.kind === "error") {
    let msg: string;
    if (KNOWN_ERRORS.has(state.message)) {
      msg = t(`routes.testErrors.${state.message}` as Parameters<typeof t>[0]);
    } else {
      const invalidModel = state.message.match(/^unsupported model:\s*(.+)$/i);
      msg = invalidModel
        ? t("routes.testErrors.invalid_model", { model: invalidModel[1] })
        : state.message;
    }
    return <p className="text-2xs text-error mt-1">{msg}</p>;
  }
  return null;
}
