"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { notifyWorkspaceLabelsChanged } from "@/hooks/useWorkspaceLabel";

interface Pair {
  singular: string;
  plural: string;
}

interface Labels {
  de: Pair;
  en: Pair;
}

const DEFAULTS: Labels = {
  de: { singular: "Workspace", plural: "Workspaces" },
  en: { singular: "Workspace", plural: "Workspaces" },
};

const MAX_LEN = 40;

function readPair(d: Record<string, unknown>, suffix: "de" | "en", fallback: Pair): Pair {
  const s = d[`workspace_label_singular_${suffix}`];
  const p = d[`workspace_label_plural_${suffix}`];
  return {
    singular: typeof s === "string" && s ? s : fallback.singular,
    plural: typeof p === "string" && p ? p : fallback.plural,
  };
}

function isPairValid(p: Pair): boolean {
  const s = p.singular.trim();
  const pl = p.plural.trim();
  return s.length > 0 && pl.length > 0 && s.length <= MAX_LEN && pl.length <= MAX_LEN;
}

function pairsEqual(a: Pair, b: Pair): boolean {
  return a.singular === b.singular && a.plural === b.plural;
}

function trimPair(p: Pair): Pair {
  return { singular: p.singular.trim(), plural: p.plural.trim() };
}

export default function WorkspaceLabelCard() {
  const t = useTranslations("admin");
  const [loaded, setLoaded] = useState<Labels | null>(null);
  const [de, setDe] = useState<Pair>(DEFAULTS.de);
  const [en, setEn] = useState<Pair>(DEFAULTS.en);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const next: Labels = {
          de: readPair(d, "de", DEFAULTS.de),
          en: readPair(d, "en", DEFAULTS.en),
        };
        setLoaded(next);
        setDe(next.de);
        setEn(next.en);
      })
      .catch(() => {
        setLoaded(DEFAULTS);
        setDe(DEFAULTS.de);
        setEn(DEFAULTS.en);
      });
  }, []);

  if (!loaded) return null;

  const trimmedDe = trimPair(de);
  const trimmedEn = trimPair(en);
  const dirty = !pairsEqual(trimmedDe, loaded.de) || !pairsEqual(trimmedEn, loaded.en);
  const valid = isPairValid(de) && isPairValid(en);

  async function save() {
    if (!valid || !dirty) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_label_singular_de: trimmedDe.singular,
          workspace_label_plural_de: trimmedDe.plural,
          workspace_label_singular_en: trimmedEn.singular,
          workspace_label_plural_en: trimmedEn.plural,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? t("saveFailed"));
      }
      setLoaded({ de: trimmedDe, en: trimmedEn });
      notifyWorkspaceLabelsChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  function reset() {
    setDe(DEFAULTS.de);
    setEn(DEFAULTS.en);
  }

  const atDefaults =
    pairsEqual(de, DEFAULTS.de) && pairsEqual(en, DEFAULTS.en);

  const renderSection = (
    sectionTitle: string,
    pair: Pair,
    setPair: (p: Pair) => void,
  ) => (
    <div>
      <p className="text-xs font-medium text-foreground mb-2">{sectionTitle}</p>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="block">
          <span className="block text-xs text-muted mb-1">{t("workspaceLabel.singular")}</span>
          <input
            type="text"
            value={pair.singular}
            onChange={(e) => setPair({ ...pair, singular: e.target.value.slice(0, MAX_LEN) })}
            disabled={saving}
            maxLength={MAX_LEN}
            className="w-full text-sm px-3 py-1.5 border-2 border-border rounded-md transition-colors hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50"
          />
        </label>
        <label className="block">
          <span className="block text-xs text-muted mb-1">{t("workspaceLabel.plural")}</span>
          <input
            type="text"
            value={pair.plural}
            onChange={(e) => setPair({ ...pair, plural: e.target.value.slice(0, MAX_LEN) })}
            disabled={saving}
            maxLength={MAX_LEN}
            className="w-full text-sm px-3 py-1.5 border-2 border-border rounded-md transition-colors hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50"
          />
        </label>
      </div>
    </div>
  );

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-sm font-medium text-foreground">{t("workspaceLabel.title")}</p>
      <p className="text-xs text-muted mt-1 mb-4">{t("workspaceLabel.description")}</p>
      <div className="flex flex-col gap-4">
        {renderSection(t("workspaceLabel.deSection"), de, setDe)}
        {renderSection(t("workspaceLabel.enSection"), en, setEn)}
      </div>
      <div className="flex items-center justify-between gap-3 mt-4">
        <button
          type="button"
          onClick={reset}
          disabled={saving || atDefaults}
          className="text-xs text-muted hover:text-kb disabled:opacity-40 disabled:hover:text-muted"
        >
          {t("reset")}
        </button>
        <div className="flex items-center gap-3">
          {error && <span className="text-xs text-error">{error}</span>}
          <button
            type="button"
            onClick={save}
            disabled={saving || !dirty || !valid}
            className="btn-primary px-3 py-1.5 text-xs font-medium rounded-md disabled:opacity-40"
          >
            {saving ? t("ellipsis") : t("save")}
          </button>
        </div>
      </div>
    </div>
  );
}
