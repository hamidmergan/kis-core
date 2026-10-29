"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { CaretDown, CaretUp, CheckCircle, Lightning, Spinner, Warning, XCircle } from "@phosphor-icons/react";
import Checkbox from "@/components/ui/Checkbox";
import HelpTooltip from "@/components/ui/HelpTooltip";
import { testFeatureRoute } from "./_api";
import DefaultVoiceRow from "./DefaultVoiceRow";
import { eligibleProviders, modelsOf, orderedProviders } from "./_routeOptions";
import type { Feature, FeatureRoute, Provider, ProviderMeta, Sampling } from "./_types";

type Props = {
  meta: ProviderMeta;
  providers: Provider[];
  routes: FeatureRoute[];
  onChangeProviderModel: (feature: Feature, providerId: number, modelName: string | null) => Promise<void>;
  onChangeSampling: (feature: Feature, providerId: number, werte: Sampling | null) => Promise<void>;
  onToggleUserChoice: (feature: Feature, providerId: number, on: boolean) => Promise<void>;
  onMove: (feature: Feature, providerId: number, step: -1 | 1) => Promise<void>;
};

// Only these features run via chat/completions, only there do the values apply.
const CHAT_LIKE: ReadonlySet<string> = new Set([
  "chat", "vision", "ocr", "doc_translate", "transcript_translate",
]);

const FELD =
  "w-16 text-xs px-1.5 py-1 border-2 border-border rounded-md font-mono text-center " +
  "hover:border-kb focus:outline-none focus:border-kb bg-background " +
  "disabled:opacity-60 disabled:cursor-not-allowed";

function SamplingRow({
  werte,
  disabled,
  onChange,
}: {
  werte: Sampling | undefined;
  disabled: boolean;
  onChange: (werte: Sampling | null) => void;
}) {
  const t = useTranslations("admin.providers");
  const setze = (schluessel: "temperature" | "top_p", roh: string) => {
    const naechste: Sampling = { ...(werte ?? {}) };
    const zahl = roh.trim() === "" ? NaN : Number(roh);
    if (Number.isNaN(zahl)) delete naechste[schluessel];
    else naechste[schluessel] = zahl;
    onChange(Object.keys(naechste).length ? naechste : null);
  };
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-2xs text-muted-soft whitespace-nowrap">{t("routes.temperature")}</span>
      <input
        key={`temp-${werte?.temperature ?? ""}`}
        type="number" step="0.05" min="0" max="2" disabled={disabled}
        defaultValue={werte?.temperature ?? ""}
        onBlur={(e) => setze("temperature", e.target.value)}
        placeholder={t("routes.samplingAuto")}
        className={FELD}
      />
      <span className="text-2xs text-muted-soft whitespace-nowrap">top_p</span>
      <input
        key={`topp-${werte?.top_p ?? ""}`}
        type="number" step="0.05" min="0" max="1" disabled={disabled}
        defaultValue={werte?.top_p ?? ""}
        onBlur={(e) => setze("top_p", e.target.value)}
        placeholder={t("routes.samplingAuto")}
        className={FELD}
      />
    </div>
  );
}

// A set value stays visible even when the fine tuning is folded away.
function hatWerte(werte: Sampling | undefined): boolean {
  return werte?.temperature != null || werte?.top_p != null;
}

type ProviderTestStates = Record<number, TestState>;

type TestState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ok" }
  | { kind: "warning"; message: string }
  | { kind: "error"; message: string };

// Display order in the routing table.
const FEATURE_ORDER: Feature[] = [
  "chat",
  "embedding",
  "vision",
  "image_gen",
  "image_edit",
  "ocr",
  "stt",
  "tts",
  "doc_translate",
  "transcript_translate",
];

// Features with a user choice that list their providers, the others show toggles.
const SPLIT_USER_CHOICE_FEATURES: ReadonlySet<Feature> = new Set([
  "tts",
  "vision",
  "image_gen",
  "image_edit",
  "doc_translate",
]);

export default function FeatureRoutingCard({
  meta,
  providers,
  routes,
  onChangeProviderModel,
  onChangeSampling,
  onToggleUserChoice,
  onMove,
}: Props) {
  const t = useTranslations("admin.providers");
  const [testStates, setTestStates] = useState<Record<string, TestState>>({});
  const [runAllBusy, setRunAllBusy] = useState(false);
  // Empty sampling rows on every feature look like clutter, so they stay folded away.
  const [feinAn, setFeinAn] = useState(false);

  const routeByFeature = useMemo(() => {
    const m = new Map<Feature, FeatureRoute>();
    for (const r of routes) m.set(r.feature, r);
    return m;
  }, [routes]);

  const providerById = useMemo(() => {
    const m = new Map<number, Provider>();
    for (const p of providers) m.set(p.id, p);
    return m;
  }, [providers]);

  const resultToState = (res: { status: "ok" | "error"; error: string | null; warning?: string | null }): TestState => {
    if (res.status === "ok") {
      return res.warning ? { kind: "warning", message: res.warning } : { kind: "ok" };
    }
    return { kind: "error", message: res.error || "unknown error" };
  };

  const onTest = useCallback(async (feature: Feature) => {
    setTestStates((s) => ({ ...s, [feature]: { kind: "running" } }));
    try {
      const res = await testFeatureRoute(feature);
      setTestStates((s) => ({ ...s, [feature]: resultToState(res) }));
    } catch (e) {
      setTestStates((s) => ({
        ...s,
        [feature]: { kind: "error", message: (e as Error).message || "request failed" },
      }));
    }
  }, []);

  const onTestProvider = useCallback(async (feature: Feature, providerId: number) => {
    const key = `${feature}-${providerId}`;
    setTestStates((s) => ({ ...s, [key]: { kind: "running" } }));
    try {
      const res = await testFeatureRoute(feature, providerId);
      setTestStates((s) => ({ ...s, [key]: resultToState(res) }));
    } catch (e) {
      setTestStates((s) => ({
        ...s,
        [key]: { kind: "error", message: (e as Error).message || "request failed" },
      }));
    }
  }, []);

  const onRunAll = useCallback(async () => {
    if (runAllBusy) return;
    setRunAllBusy(true);
    try {
      const orderedFeatures = FEATURE_ORDER.filter((f) => meta.features.includes(f));
      for (const feature of orderedFeatures) {
        const route = routes.find((r) => r.feature === feature);
        // Rows that list their providers test each of them, the toggle rows test the route once.
        if (!meta.user_choice_features.includes(feature) || SPLIT_USER_CHOICE_FEATURES.has(feature)) {
          for (const p of eligibleProviders(feature, providers)) {
            await onTestProvider(feature, p.id);
          }
        } else {
          if (route?.provider_id == null) continue;
          await onTest(feature);
        }
      }
    } finally {
      setRunAllBusy(false);
    }
  }, [runAllBusy, meta.features, meta.user_choice_features, routes, providers, onTest, onTestProvider]);

  return (
    <section className="border border-border-soft rounded-xl bg-background p-5">
      <div className="flex items-start justify-between gap-4 mb-1">
        <p className="text-sm font-medium text-foreground">{t("routes.title")}</p>
        <button
          type="button"
          onClick={onRunAll}
          disabled={runAllBusy}
          title={t("routes.testAll")}
          aria-label={t("routes.testAll")}
          className="shrink-0 w-8 h-8 rounded-md border border-border-soft bg-background flex items-center justify-center text-muted hover:text-kb hover:outline hover:outline-2 hover:outline-kb transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {runAllBusy ? (
            <Spinner size={14} weight="bold" className="animate-spin" />
          ) : (
            <Lightning size={14} weight="bold" />
          )}
        </button>
      </div>
      <p className="text-xs text-muted-soft mb-2 max-w-2xl">{t("routes.hint")}</p>

      <div className="flex items-center justify-end gap-1.5 mb-2">
        <Checkbox
          checked={feinAn}
          onChange={setFeinAn}
          label={t("routes.samplingToggle")}
          labelClassName="text-xs text-muted-soft"
        />
        <HelpTooltip text={t("routes.samplingHelp")} />
      </div>

      <div className="divide-y divide-border-soft">
        {FEATURE_ORDER.filter((f) => meta.features.includes(f)).map((feature) => {
          const route = routeByFeature.get(feature);
          const isUserChoice = meta.user_choice_features.includes(feature);
          // The rows come in the admin's order, the first usable one is the standard.
          const eligible = orderedProviders(feature, route, providers);

          const providerTestStates: ProviderTestStates = Object.fromEntries(
            eligible.map((p) => [p.id, testStates[`${feature}-${p.id}`] ?? { kind: "idle" as const }])
          );
          return (
            <FeatureRow
              key={feature}
              feature={feature}
              route={route}
              eligible={eligible}
              providerById={providerById}
              isUserChoice={isUserChoice}
              testState={testStates[feature] ?? { kind: "idle" }}
              providerTestStates={providerTestStates}
              testsLocked={runAllBusy}
              onTest={() => onTest(feature)}
              onTestProvider={(pid) => onTestProvider(feature, pid)}
              onChangeProviderModel={(pid, model) => onChangeProviderModel(feature, pid, model)}
              onChangeSampling={(pid, werte) => onChangeSampling(feature, pid, werte)}
              onToggleUserChoice={(pid, on) => onToggleUserChoice(feature, pid, on)}
              onMove={(pid, step) => onMove(feature, pid, step)}
              feinAn={feinAn}
            />
          );
        })}
      </div>
    </section>
  );
}

function FeatureRow({
  feature,
  route,
  eligible,
  providerById,
  isUserChoice,
  testState,
  providerTestStates,
  testsLocked,
  onTest,
  onTestProvider,
  onChangeProviderModel,
  onChangeSampling,
  onToggleUserChoice,
  onMove,
  feinAn,
}: {
  feature: Feature;
  route: FeatureRoute | undefined;
  eligible: Provider[];
  providerById: Map<number, Provider>;
  isUserChoice: boolean;
  testState: TestState;
  providerTestStates: ProviderTestStates;
  testsLocked: boolean;
  onTest: () => void;
  onTestProvider: (providerId: number) => void;
  onChangeProviderModel: (providerId: number, model: string | null) => void;
  onChangeSampling: (providerId: number, werte: Sampling | null) => void;
  onToggleUserChoice: (id: number, on: boolean) => void;
  onMove: (id: number, step: -1 | 1) => void;
  feinAn: boolean;
}) {
  const t = useTranslations("admin.providers");
  const providerId = route?.provider_id ?? null;
  const provider = providerId != null ? providerById.get(providerId) : undefined;
  const userChoices = route?.user_choices ?? [];
  const canTest = providerId != null;
  const models = modelsOf(route);

  if (isUserChoice && !SPLIT_USER_CHOICE_FEATURES.has(feature)) {
    const primary = provider;
    const primaryNeedsModel = primary?.protocol === "openai_compat";
    return (
      <div className="py-4 flex flex-col gap-3 sm:grid sm:grid-cols-[1fr_auto] sm:gap-4 sm:items-start">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">{t(`featureName.${feature}`)}</p>
          <TestStatusLine state={testState} />
        </div>
        <div className="flex flex-col gap-2 sm:items-end sm:max-w-115">
          <div className="flex flex-wrap gap-2 items-center sm:justify-end">
            {eligible.length === 0 ? (
              <span className="text-2xs text-muted-soft italic">{t("routes.noEligible")}</span>
            ) : (
              eligible.map((p) => {
                const on = userChoices.includes(p.id);
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => onToggleUserChoice(p.id, !on)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md border-2 transition-colors ${
                      on
                        ? "border-kb bg-[rgba(var(--kb-rgb),0.07)] text-kb"
                        : "border-border bg-background text-foreground-soft hover:border-kb"
                    }`}
                  >
                    {p.name}
                  </button>
                );
              })
            )}
          </div>
          {primary && (
            <div className="flex flex-col gap-1.5 w-full sm:flex-row sm:items-center sm:gap-2">
              <label className="text-2xs text-muted-soft whitespace-nowrap sm:ml-auto">
                {t("routes.modelForPrimary", { name: primary.name })}
              </label>
              <div className="flex gap-2 items-center">
                <input
                    key={models[String(primary.id)] ?? ""}
                    type="text"
                    defaultValue={models[String(primary.id)] ?? ""}
                    onBlur={(e) => {
                      const wert = e.target.value.trim();
                      // Only a real change saves, a mere click elsewhere must not send a request.
                      if (wert !== (models[String(primary.id)] ?? "")) onChangeProviderModel(primary.id, wert || null);
                    }}
                    placeholder={primaryNeedsModel ? t("routes.modelPlaceholder") : t("routes.modelOptional")}
                    spellCheck={false}
                    className="flex-1 sm:flex-none sm:w-45 text-xs px-2 py-1.5 border-2 border-border rounded-md font-mono hover:border-kb focus:outline-none focus:border-kb bg-background"
                  />
                <TestButton state={testState} disabled={!canTest || testsLocked} onClick={onTest} />
              </div>
            </div>
          )}
          {primary && CHAT_LIKE.has(feature) && primary.protocol === "openai_compat" &&
            (feinAn || hatWerte(route?.provider_sampling?.[String(primary.id)])) && (
            <div className="flex justify-end pr-1">
              <SamplingRow
                werte={route?.provider_sampling?.[String(primary.id)]}
                disabled={false}
                onChange={(werte) => onChangeSampling(primary.id, werte)}
              />
            </div>
          )}
          {!primary && (
            <TestButton state={testState} disabled={!canTest || testsLocked} onClick={onTest} />
          )}
        </div>
      </div>
    );
  }

  // Every other feature lists its providers in order, the first one with a model is the standard.
  return (
    <div className="py-4 flex flex-col gap-2">
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{t(`featureName.${feature}`)}</p>
      </div>
      <div className="flex flex-col gap-3 sm:gap-1.5 mt-1">
        {eligible.length === 0 ? (
          <span className="text-2xs text-muted-soft italic">{t("routes.noEligible")}</span>
        ) : (
          eligible.map((p, i) => {
            const isFirst = p.id === providerId;
            const modelVal = models[String(p.id)] ?? "";
            const pState = providerTestStates[p.id] ?? { kind: "idle" as const };
            return (
              <div key={p.id} className="flex flex-col gap-0.5">
                <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-2">
                  <span className={`sm:flex-1 min-w-0 truncate text-sm ${isFirst ? "font-medium text-foreground" : "text-foreground-soft"}`}>
                    <span className="font-mono text-2xs text-muted-soft mr-2">{i + 1}</span>
                    {p.name}
                    {isFirst && <span className="ml-2 text-2xs font-normal text-kb">{t("routes.standard")}</span>}
                  </span>
                  <div className="sm:flex-1 min-w-0 flex items-center gap-2">
                    <input
                      key={`${p.id}-${modelVal}`}
                      type="text"
                      defaultValue={modelVal}
                      onBlur={(e) => {
                        const wert = e.target.value.trim();
                        // Only a real change saves, a mere click on an arrow must not send a second request.
                        if (wert !== modelVal) onChangeProviderModel(p.id, wert || null);
                      }}
                      placeholder={p.protocol === "openai_compat" ? t("routes.modelPlaceholder") : t("routes.modelOptional")}
                      spellCheck={false}
                      className="flex-1 min-w-0 text-xs px-2 py-1.5 border-2 border-border rounded-md font-mono hover:border-kb focus:outline-none focus:border-kb bg-background text-left"
                    />
                    <MoveButton direction="up" disabled={i === 0} onClick={() => onMove(p.id, -1)} />
                    <MoveButton direction="down" disabled={i === eligible.length - 1} onClick={() => onMove(p.id, 1)} />
                    <TestButton state={pState} disabled={testsLocked} onClick={() => onTestProvider(p.id)} />
                  </div>
                </div>
                {CHAT_LIKE.has(feature) && p.protocol === "openai_compat" &&
                  (feinAn || hatWerte(route?.provider_sampling?.[String(p.id)])) && (
                  <div className="flex justify-end pr-1">
                    <SamplingRow
                      werte={route?.provider_sampling?.[String(p.id)]}
                      disabled={false}
                      onChange={(werte) => onChangeSampling(p.id, werte)}
                    />
                  </div>
                )}
                <TestStatusLine state={pState} />
              </div>
            );
          })
        )}
      </div>
      {/* The default voice depends on the providers and belongs here, not in a separate card. It picks provider and voice in ONE field because a user-selects feature has no single routed provider to attach to. */}
      {feature === "tts" && <DefaultVoiceRow eligible={eligible} starId={providerId} />}
    </div>
  );
}

function MoveButton({ direction, disabled, onClick }: { direction: "up" | "down"; disabled: boolean; onClick: () => void }) {
  const t = useTranslations("admin.providers");
  const label = direction === "up" ? t("routes.moveUp") : t("routes.moveDown");
  const Icon = direction === "up" ? CaretUp : CaretDown;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className="w-8 h-8 shrink-0 rounded-md border border-border-soft bg-background flex items-center justify-center text-muted transition-colors enabled:hover:text-kb enabled:hover:outline enabled:hover:outline-2 enabled:hover:outline-kb disabled:opacity-40 disabled:cursor-not-allowed"
    >
      <Icon size={14} weight="bold" />
    </button>
  );
}

function TestButton({
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

function TestStatusLine({ state }: { state: TestState }) {
  const t = useTranslations("admin.providers");
  if (state.kind === "ok") {
    return <p className="text-2xs text-success mt-1">{t("routes.testOk")}</p>;
  }
  if (state.kind === "warning") {
    const knownWarnings = new Set([
      "stt_model_not_validated_by_provider",
      "stt_endpoint_verified_model_unvalidated",
    ]);
    const msg = knownWarnings.has(state.message)
      ? t(`routes.testErrors.${state.message}` as Parameters<typeof t>[0])
      : state.message;
    return <p className="text-2xs text-warn mt-1">{msg}</p>;
  }
  if (state.kind === "error") {
    const knownCodes = new Set([
      "model_name_not_set",
      "tts_speech_endpoint_not_found",
      "endpoint_not_found",
      "auth_rejected",
      "server_error",
      "unreachable",
      "no_voices_configured",
    ]);
    let msg: string;
    if (knownCodes.has(state.message)) {
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

