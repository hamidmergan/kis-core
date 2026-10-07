"use client";

/** Create and edit the one evaluation, and switch it on or off. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Trash } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import ToggleRow from "@/components/ui/ToggleRow";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";

type FrageTyp = "choice" | "multi" | "text";
type ShowIf = { question_id: string; in: string[] };

type Frage = {
  id: string;
  type: FrageTyp;
  text: string;
  options?: string[];
  show_if?: ShowIf;
};

type Config = {
  active: boolean;
  for_all: boolean;
  title: string;
  intro_text: string;
  intro_link_label: string;
  intro_link_url: string;
  outro_text: string;
  outro_link_label: string;
  outro_link_url: string;
  contact_email: string;
  questions: Frage[];
};

let lokaleZaehler = 0;
function neueLokaleId(): string {
  lokaleZaehler += 1;
  return `neu-${lokaleZaehler}`;
}

export default function EvaluationTab() {
  const t = useTranslations("admin.evaluationEditor");
  const [config, setConfig] = useState<Config | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch("/api/admin/evaluation", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: Config | null) => { if (d) setConfig(d); })
      .catch(() => {});
  }, []);

  async function toggleActive(active: boolean) {
    if (!config) return;
    setConfig({ ...config, active });
    try {
      await fetch("/api/admin/evaluation/active", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active }),
      });
    } catch {
      setConfig({ ...config, active: !active });
    }
  }

  async function toggleForAll(for_all: boolean) {
    if (!config) return;
    setConfig({ ...config, for_all });
    try {
      await fetch("/api/admin/evaluation/for-all", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ for_all }),
      });
    } catch {
      setConfig({ ...config, for_all: !for_all });
    }
  }

  function addQuestion() {
    if (!config) return;
    setConfig({
      ...config,
      questions: [...config.questions, { id: neueLokaleId(), type: "text", text: "" }],
    });
  }

  function removeQuestion(id: string) {
    if (!config) return;
    setConfig({ ...config, questions: config.questions.filter((f) => f.id !== id) });
  }

  function updateQuestion(id: string, patch: Partial<Frage>) {
    if (!config) return;
    setConfig({
      ...config,
      questions: config.questions.map((f) => (f.id === id ? { ...f, ...patch } : f)),
    });
  }

  async function save() {
    if (!config) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const r = await fetch("/api/admin/evaluation", {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: config.title,
          intro_text: config.intro_text,
          intro_link_label: config.intro_link_label,
          intro_link_url: config.intro_link_url,
          outro_text: config.outro_text,
          outro_link_label: config.outro_link_label,
          outro_link_url: config.outro_link_url,
          contact_email: config.contact_email,
          // id and show_if ride along unchanged, so existing conditionals and
          // past answers still match after a save that only touches other fields.
          questions: config.questions.map((frage) => ({
            ...frage,
            options: frage.options ?? [],
          })),
        }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(typeof body?.detail === "string" ? body.detail : t("saveError"));
        return;
      }
      const saved: Config = await r.json();
      setConfig(saved);
      setSaved(true);
    } catch {
      setError(t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  if (!config) {
    return (
      <div className="flex justify-center py-12">
        <Spinner label={t("loading")} />
      </div>
    );
  }

  const typOptionen = [
    { value: "choice" as const, label: t("typeChoice") },
    { value: "multi" as const, label: t("typeMulti") },
    { value: "text" as const, label: t("typeText") },
  ];

  return (
    <div className="max-w-2xl space-y-6">
      <div
        className="rounded-xl p-4"
        style={{ backgroundColor: "var(--surface-dim)", border: "1px solid var(--border-soft)" }}
      >
        <ToggleRow
          title={t("activeLabel")}
          description={t("activeHint")}
          checked={config.active}
          onToggle={() => toggleActive(!config.active)}
        />
        <div className="mt-4 pt-4" style={{ borderTop: "1px solid var(--border-soft)" }}>
          <ToggleRow
            title={t("forAllLabel")}
            description={t("forAllHint")}
            checked={config.for_all}
            onToggle={() => toggleForAll(!config.for_all)}
          />
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-xs uppercase tracking-wide text-muted">{t("titleLabel")}</label>
        <input
          value={config.title}
          onChange={(e) => setConfig({ ...config, title: e.target.value })}
          className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
      </div>

      <fieldset className="min-w-0 space-y-2 border border-border-soft rounded-xl p-4">
        <legend className="text-xs uppercase tracking-wide text-muted px-1">{t("introLegend")}</legend>
        <textarea
          value={config.intro_text}
          onChange={(e) => setConfig({ ...config, intro_text: e.target.value })}
          rows={3}
          placeholder={t("introTextPlaceholder")}
          className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb resize-none"
        />
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            value={config.intro_link_label}
            onChange={(e) => setConfig({ ...config, intro_link_label: e.target.value })}
            placeholder={t("linkLabelPlaceholder")}
            className="min-w-0 flex-1 text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
          />
          <input
            value={config.intro_link_url}
            onChange={(e) => setConfig({ ...config, intro_link_url: e.target.value })}
            placeholder={t("linkUrlPlaceholder")}
            className="min-w-0 flex-1 text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
          />
        </div>
      </fieldset>

      <div className="space-y-2">
        <label className="text-xs uppercase tracking-wide text-muted">{t("questionsLabel")}</label>
        <div className="space-y-4">
          {config.questions.map((frage) => (
            <div key={frage.id} className="flex flex-col gap-2 border border-border-soft rounded-xl p-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
                <Select
                  value={frage.type}
                  onChange={(value) => updateQuestion(frage.id, { type: value })}
                  options={typOptionen}
                  className="w-full sm:w-44 sm:flex-shrink-0"
                />
                <div className="flex min-w-0 flex-1 items-start gap-2">
                  <input
                    value={frage.text}
                    onChange={(e) => updateQuestion(frage.id, { text: e.target.value })}
                    placeholder={t("questionTextPlaceholder")}
                    className="min-w-0 flex-1 text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
                  />
                  <IconButton onClick={() => removeQuestion(frage.id)} aria-label={t("removeQuestion")}>
                    <Trash size={14} weight="bold" />
                  </IconButton>
                </div>
              </div>
              {/* Only choice and multi pick from a fixed list, a free text field has none. */}
              {frage.type !== "text" && (
                <>
                  <textarea
                    value={(frage.options ?? []).join("\n")}
                    onChange={(e) => updateQuestion(frage.id, { options: e.target.value.split("\n") })}
                    rows={3}
                    placeholder={t("optionsPlaceholder")}
                    className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb resize-none"
                  />
                </>
              )}
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addQuestion}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
        >
          <Plus size={14} weight="bold" />
          {t("addQuestion")}
        </button>
      </div>

      <fieldset className="min-w-0 space-y-2 border border-border-soft rounded-xl p-4">
        <legend className="text-xs uppercase tracking-wide text-muted px-1">{t("outroLegend")}</legend>
        <textarea
          value={config.outro_text}
          onChange={(e) => setConfig({ ...config, outro_text: e.target.value })}
          rows={3}
          placeholder={t("outroTextPlaceholder")}
          className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb resize-none"
        />
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            value={config.outro_link_label}
            onChange={(e) => setConfig({ ...config, outro_link_label: e.target.value })}
            placeholder={t("linkLabelPlaceholder")}
            className="min-w-0 flex-1 text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
          />
          <input
            value={config.outro_link_url}
            onChange={(e) => setConfig({ ...config, outro_link_url: e.target.value })}
            placeholder={t("linkUrlPlaceholder")}
            className="min-w-0 flex-1 text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
          />
        </div>
        <input
          value={config.contact_email}
          onChange={(e) => setConfig({ ...config, contact_email: e.target.value })}
          placeholder={t("contactEmailPlaceholder")}
          className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
      </fieldset>

      {error && <p className="text-sm text-error">{error}</p>}

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={saving || !config.title.trim() || config.questions.length === 0}
          className="px-4 py-2 text-sm btn-primary rounded-md transition-colors disabled:opacity-60"
        >
          {saving ? t("saving") : t("save")}
        </button>
        {saved && <p className="text-xs" style={{ color: "var(--foreground-soft)" }}>{t("savedHint")}</p>}
      </div>
    </div>
  );
}
