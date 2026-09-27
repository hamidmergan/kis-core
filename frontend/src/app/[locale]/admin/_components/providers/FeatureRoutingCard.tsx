"use client";

import { useCallback, useId, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { CheckCircle, Lightning, Spinner, Warning, XCircle } from "@phosphor-icons/react";
import Checkbox from "@/components/ui/Checkbox";
import HelpTooltip from "@/components/ui/HelpTooltip";
import { testFeatureRoute } from "./_api";
import DefaultVoiceRow from "./DefaultVoiceRow";
import { fallbackOptions, firstChoiceOptions, type FallbackOption } from "./_routeOptions";
import type { Capability, Feature, FeatureRoute, Provider, ProviderMeta, Sampling } from "./_types";

type Props = {
  meta: ProviderMeta;
  providers: Provider[];
  routes: FeatureRoute[];
  onChangeProvider: (feature: Feature, providerId: number | null) => Promise<void>;
  onChangeModel: (feature: Feature, modelName: string | null) => Promise<void>;
  onChangeProviderModel: (feature: Feature, providerId: number, modelName: string | null) => Promise<void>;
  onChangeSampling: (feature: Feature, providerId: number, werte: Sampling | null) => Promise<void>;
  onToggleUserChoice: (feature: Feature, providerId: number, on: boolean) => Promise<void>;
  onChangeFallback: (feature: Feature, providerId: number | null) => Promise<void>;
};

// Nur diese Funktionen laufen ueber chat/completions, nur dort wirken die Werte.
const CHAT_LIKE: ReadonlySet<string> = new Set([
  "chat", "vision", "ocr", "doc_translate", "transcript_translate",
]);

const FELD =
  "w-16 text-xs px-1.5 py-1 border-2 border-border rounded-md font-mono text-center " +
  "hover:border-kb focus:outline-none focus:border-kb bg-background " +
  "disabled:opacity-60 disabled:cursor-not-allowed";

// The native provider dropdown of this card, callers add the width.
const AUSWAHL =
  "min-w-0 text-xs px-2 py-1.5 border-2 border-border rounded-md hover:border-kb " +
  "focus:outline-none focus:border-kb bg-background disabled:opacity-60 disabled:cursor-not-allowed";

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

// One capability per feature, the provider list filters by it.
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

// For translating a chat capable provider counts too.
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

// Features with a user choice test every provider separately, the others once.
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
  onChangeSampling,
  onToggleUserChoice,
  onChangeFallback,
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
          // Without the list from the server the backend cannot take a fallback yet.
          const hasFallback = (meta.fallback_features ?? []).includes(feature);
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
              onChangeSampling={(pid, werte) => onChangeSampling(feature, pid, werte)}
              onToggleUserChoice={(pid, on) => onToggleUserChoice(feature, pid, on)}
              fallback={hasFallback ? fallbackOptions(feature, route, providers) : null}
              onChangeFallback={(pid) => onChangeFallback(feature, pid)}
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
  onChangeProvider,
  onChangeModel,
  onChangeProviderModel,
  onChangeSampling,
  onToggleUserChoice,
  fallback,
  onChangeFallback,
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
  onChangeProvider: (id: number | null) => void;
  onChangeModel: (model: string | null) => void;
  onChangeProviderModel: (providerId: number, model: string | null) => void;
  onChangeSampling: (providerId: number, werte: Sampling | null) => void;
  onToggleUserChoice: (id: number, on: boolean) => void;
  fallback: FallbackOption[] | null;
  onChangeFallback: (id: number | null) => void;
  feinAn: boolean;
}) {
  const t = useTranslations("admin.providers");
  const firstId = useId();
  const fallbackId = useId();
  const providerId = route?.provider_id ?? null;
  const provider = providerId != null ? providerById.get(providerId) : undefined;
  const userChoices = route?.user_choices ?? [];
  const canTest = providerId != null;
  const fallbackValue = route?.fallback_provider_id ?? null;
  const fallbackModel = fallback?.find((o) => o.id === fallbackValue)?.model ?? "";

  if (isUserChoice && SPLIT_USER_CHOICE_FEATURES.has(feature)) {
    return (
      <div className="py-4 flex flex-col gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">{t(`featureName.${feature}`)}</p>
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
        {feature !== "tts" && eligible.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border-soft flex flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <label htmlFor={firstId} className="flex-1 min-w-0 truncate text-sm text-foreground-soft">
                {t("routes.firstChoice")}
              </label>
              <select
                id={firstId}
                value={providerId ?? ""}
                onChange={(e) => onChangeProvider(e.target.value ? Number(e.target.value) : null)}
                className={`${AUSWAHL} flex-1`}
              >
                <option value="">{t("routes.unselected")}</option>
                {firstChoiceOptions(route, eligible).map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
                {provider && !eligible.includes(provider) && (
                  <option value={provider.id}>{t("routes.providerUnusable", { name: provider.name })}</option>
                )}
              </select>
              {/* Keeps the dropdowns flush with the model fields above. */}
              <span className="w-8 shrink-0" aria-hidden="true" />
            </div>
            {fallback && (
              <div className="flex items-center gap-2">
                <div className="flex-1 min-w-0 flex items-center gap-1">
                  <label htmlFor={fallbackId} className="truncate text-sm text-foreground-soft">
                    {t("routes.fallback")}
                  </label>
                  <HelpTooltip text={t("routes.fallbackHelp")} />
                </div>
                <FallbackSelect
                  id={fallbackId}
                  value={fallbackValue}
                  options={fallback}
                  onChange={onChangeFallback}
                  className="flex-1"
                />
                <span className="w-8 shrink-0" aria-hidden="true" />
              </div>
            )}
          </div>
        )}
        {/* Die Standardstimme haengt an den Anbietern und gehoert deshalb hierher,
            nicht in eine eigene Karte anderswo. Sie waehlt Anbieter und Stimme in
            EINEM Feld, weil es bei einem Nutzer-waehlt-Feature keinen einen
            gerouteten Anbieter gibt, an den sie sich haengen koennte. */}
        {feature === "tts" && <DefaultVoiceRow eligible={eligible} />}
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

  return (
    <div className="py-4 flex flex-col gap-3 sm:grid sm:grid-cols-[1fr_180px_220px_auto] sm:items-end sm:gap-3">
      <div className="min-w-0 sm:self-center">
        <p className="text-sm font-medium text-foreground">{t(`featureName.${feature}`)}</p>
        <TestStatusLine state={testState} />
      </div>
      <div className="flex gap-2 items-end sm:contents">
        <div className="flex-1 min-w-0 flex flex-col gap-1">
          <label htmlFor={firstId} className="text-2xs text-muted-soft whitespace-nowrap">
            {t("routes.firstChoice")}
          </label>
          <select
            id={firstId}
            value={providerId ?? ""}
            onChange={(e) => onChangeProvider(e.target.value ? Number(e.target.value) : null)}
            disabled={eligible.length === 0}
            className={`${AUSWAHL} w-full`}
          >
            <option value="">{t("routes.unselected")}</option>
            {eligible.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
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
      {CHAT_LIKE.has(feature) && provider?.protocol === "openai_compat" &&
        (feinAn || (providerId != null && hatWerte(route?.provider_sampling?.[String(providerId)]))) && (
        <div className="sm:col-start-3 sm:col-span-2 flex sm:justify-start">
          <SamplingRow
            werte={providerId != null ? route?.provider_sampling?.[String(providerId)] : undefined}
            disabled={!provider}
            onChange={(werte) => providerId != null && onChangeSampling(providerId, werte)}
          />
        </div>
      )}
      {fallback && (
        <>
          <div className="min-w-0 flex flex-col gap-1 sm:col-start-2">
            <div className="flex items-center gap-1">
              <label htmlFor={fallbackId} className="text-2xs text-muted-soft whitespace-nowrap">
                {t("routes.fallback")}
              </label>
              <HelpTooltip text={`${t("routes.fallbackHelp")} ${t("routes.fallbackHelpModel")}`} />
            </div>
            <FallbackSelect
              id={fallbackId}
              value={fallbackValue}
              options={fallback}
              onChange={onChangeFallback}
              className="w-full"
            />
          </div>
          {/* The fallback's model is read only here, it is entered while that provider is the first choice. */}
          {fallbackModel && (
            <span className="truncate text-xs font-mono text-muted-soft sm:px-2 sm:py-1.5">{fallbackModel}</span>
          )}
        </>
      )}
    </div>
  );
}

function FallbackSelect({
  id,
  value,
  options,
  onChange,
  className,
}: {
  id: string;
  value: number | null;
  options: FallbackOption[];
  onChange: (id: number | null) => void;
  className: string;
}) {
  const t = useTranslations("admin.providers");
  return (
    <select
      id={id}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      disabled={options.length === 0 && value == null}
      className={`${AUSWAHL} ${className}`}
    >
      <option value="">{t("routes.noFallback")}</option>
      {options.map((o) => (
        <option key={o.id} value={o.id}>
          {o.usable ? o.name : t("routes.providerUnusable", { name: o.name })}
        </option>
      ))}
    </select>
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

