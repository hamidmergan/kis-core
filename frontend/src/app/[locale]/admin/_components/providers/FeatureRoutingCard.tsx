"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { CheckCircle, Lightning, Spinner, Warning, XCircle } from "@phosphor-icons/react";
import { testFeatureRoute } from "./_api";
import type { Capability, Feature, FeatureRoute, Provider, ProviderMeta } from "./_types";

type Props = {
  meta: ProviderMeta;
  providers: Provider[];
  routes: FeatureRoute[];
  onChangeProvider: (feature: Feature, providerId: number | null) => Promise<void>;
  onChangeModel: (feature: Feature, modelName: string | null) => Promise<void>;
  onChangeProviderModel: (feature: Feature, providerId: number, modelName: string | null) => Promise<void>;
  onToggleUserChoice: (feature: Feature, providerId: number, on: boolean) => Promise<void>;
};

type ProviderTestStates = Record<number, TestState>;

type TestState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ok" }
  | { kind: "warning"; message: string }
  | { kind: "error"; message: string };

// Each feature is satisfied by one capability. Used to filter the provider
// dropdown down to providers that actually offer the feature.
const FEATURE_CAPABILITY: Record<Feature, Capability> = {
  chat: "chat",
  embedding: "embedding",
  vision: "vision",
  ocr: "ocr",
  stt: "stt",
  tts: "tts",
  image_gen: "image_gen",
  image_edit: "image_edit",
  doc_translate: "translation",
  screencast_translate: "translation",
  transcript_translate: "translation",
};

// For translation features the dropdown should also accept any chat-capable
// provider (LLM-driven translation). This widens the capability check.
const FEATURE_EXTRA_CAPABILITIES: Partial<Record<Feature, Capability[]>> = {
  doc_translate: ["chat"],
  screencast_translate: ["chat"],
  transcript_translate: ["chat"],
};

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

// Split user-choice features test each eligible provider individually
// (per-provider model). Other features test the row's resolved provider once.
// STT is a single global-default feature (provider dropdown + model field), so
// it is not listed here — its "test" runs once on the resolved route.
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
  onChangeProvider,
  onChangeModel,
  onChangeProviderModel,
  onToggleUserChoice,
}: Props) {
  const t = useTranslations("admin.providers");
  const [testStates, setTestStates] = useState<Record<string, TestState>>({});
  const [runAllBusy, setRunAllBusy] = useState(false);

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
        if (SPLIT_USER_CHOICE_FEATURES.has(feature)) {
          const eligible = providers.filter((p) => {
            if (!p.enabled) return false;
            const caps = new Set(p.capabilities);
            if (caps.has(FEATURE_CAPABILITY[feature])) return true;
            const extras = FEATURE_EXTRA_CAPABILITIES[feature] || [];
            return extras.some((c) => caps.has(c));
          });
          for (const p of eligible) {
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
  }, [runAllBusy, meta.features, routes, providers, onTest, onTestProvider]);

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
      <p className="text-xs text-muted-soft mb-4 max-w-2xl">{t("routes.hint")}</p>

      <div className="divide-y divide-border-soft">
        {FEATURE_ORDER.filter((f) => meta.features.includes(f)).map((feature) => {
          const route = routeByFeature.get(feature);
          const isUserChoice = meta.user_choice_features.includes(feature);
          const eligible = providers.filter((p) => {
            if (!p.enabled) return false;
            const caps = new Set(p.capabilities);
            if (caps.has(FEATURE_CAPABILITY[feature])) return true;
            const extras = FEATURE_EXTRA_CAPABILITIES[feature] || [];
            return extras.some((c) => caps.has(c));
          });

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
              onChangeProvider={(pid) => onChangeProvider(feature, pid)}
              onChangeModel={(model) => onChangeModel(feature, model)}
              onChangeProviderModel={(pid, model) => onChangeProviderModel(feature, pid, model)}
              onToggleUserChoice={(pid, on) => onToggleUserChoice(feature, pid, on)}
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
  onChangeProvider,
  onChangeModel,
  onChangeProviderModel,
  onToggleUserChoice,
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
  onChangeProvider: (id: number | null) => void;
  onChangeModel: (model: string | null) => void;
  onChangeProviderModel: (providerId: number, model: string | null) => void;
  onToggleUserChoice: (id: number, on: boolean) => void;
}) {
  const t = useTranslations("admin.providers");
  const providerId = route?.provider_id ?? null;
  const provider = providerId != null ? providerById.get(providerId) : undefined;
  const userChoices = route?.user_choices ?? [];
  const canTest = providerId != null;

  if (isUserChoice && SPLIT_USER_CHOICE_FEATURES.has(feature)) {
    return (
      <div className="py-4 flex flex-col gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">{t(`featureName.${feature}`)}</p>
          <p className="text-xs text-muted-soft mt-0.5">{t(`featureDesc.${feature}`)}</p>
        </div>
        <div className="flex flex-col gap-1.5 mt-1">
          {eligible.length === 0 ? (
            <span className="text-2xs text-muted-soft italic">{t("routes.noEligible")}</span>
          ) : (
            eligible.map((p) => {
              const modelVal = route?.provider_models?.[String(p.id)] ?? "";
              const pState = providerTestStates[p.id] ?? { kind: "idle" as const };
              return (
                <div key={p.id} className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <span className="flex-1 min-w-0 truncate text-sm text-foreground-soft">{p.name}</span>
                    <input
                      key={`${p.id}-${modelVal}`}
                      type="text"
                      defaultValue={modelVal}
                      onBlur={(e) => onChangeProviderModel(p.id, e.target.value.trim() || null)}
                      placeholder={t("routes.modelOptional")}
                      spellCheck={false}
                      className="flex-1 text-xs px-2 py-1.5 border-2 border-border rounded-md font-mono hover:border-kb focus:outline-none focus:border-kb bg-background text-left"
                    />
                    <TestButton state={pState} disabled={testsLocked} onClick={() => onTestProvider(p.id)} />
                  </div>
                  <TestStatusLine state={pState} />
                </div>
              );
            })
          )}
        </div>
      </div>
    );
  }

  if (isUserChoice) {
    const primary = provider;
    const primaryNeedsModel = primary?.protocol === "openai_compat";
    return (
      <div className="py-4 flex flex-col gap-3 sm:grid sm:grid-cols-[1fr_auto] sm:gap-4 sm:items-start">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">{t(`featureName.${feature}`)}</p>
          <p className="text-xs text-muted-soft mt-0.5">{t(`featureDesc.${feature}`)}</p>
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
                    key={route?.model_name ?? ""}
                    type="text"
                    defaultValue={route?.model_name ?? ""}
                    onBlur={(e) => onChangeModel(e.target.value.trim() || null)}
                    placeholder={primaryNeedsModel ? t("routes.modelPlaceholder") : t("routes.modelOptional")}
                    spellCheck={false}
                    className="flex-1 sm:flex-none sm:w-45 text-xs px-2 py-1.5 border-2 border-border rounded-md font-mono hover:border-kb focus:outline-none focus:border-kb bg-background"
                  />
                <TestButton state={testState} disabled={!canTest || testsLocked} onClick={onTest} />
              </div>
            </div>
          )}
          {!primary && (
            <TestButton state={testState} disabled={!canTest || testsLocked} onClick={onTest} />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="py-4 flex flex-col gap-3 sm:grid sm:grid-cols-[1fr_180px_220px_auto] sm:items-center sm:gap-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{t(`featureName.${feature}`)}</p>
        <p className="text-xs text-muted-soft mt-0.5">{t(`featureDesc.${feature}`)}</p>
        <TestStatusLine state={testState} />
      </div>
      <div className="flex gap-2 sm:contents">
        <select
          value={providerId ?? ""}
          onChange={(e) => onChangeProvider(e.target.value ? Number(e.target.value) : null)}
          disabled={eligible.length === 0}
          className="flex-1 min-w-0 text-xs px-2 py-1.5 border-2 border-border rounded-md hover:border-kb focus:outline-none focus:border-kb bg-background disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <option value="">{t("routes.unselected")}</option>
          {eligible.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          key={route?.provider_models?.[String(providerId)] ?? route?.model_name ?? ""}
          type="text"
          defaultValue={route?.provider_models?.[String(providerId)] ?? route?.model_name ?? ""}
          onBlur={(e) => onChangeModel(e.target.value.trim() || null)}
          disabled={!provider}
          placeholder={provider ? t("routes.modelPlaceholder") : "—"}
          spellCheck={false}
          className="text-xs px-2 py-1.5 border-2 border-border rounded-md font-mono hover:border-kb focus:outline-none focus:border-kb bg-background disabled:opacity-60 disabled:cursor-not-allowed"
        />
        <TestButton state={testState} disabled={!canTest || testsLocked} onClick={onTest} />
      </div>
    </div>
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

