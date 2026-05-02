"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";

interface AdminPrompt {
  key: string;
  label: string;
  description: string;
  editable: boolean;
  current_value: string;
  default_value: string;
}

export default function PromptsTab() {
  const t = useTranslations("admin");
  const [prompts, setPrompts] = useState<AdminPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await fetch("/api/admin/prompts", { credentials: "include" });
    const d = await r.json();
    const ps: AdminPrompt[] = d.prompts ?? [];
    setPrompts(ps);
    const initial: Record<string, string> = {};
    for (const p of ps) initial[p.key] = p.current_value;
    setValues(initial);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (key: string) => {
    setSaving(key);
    try {
      await fetch(`/api/admin/prompts/${key}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: values[key] }),
      });
      setSaved(key);
      setTimeout(() => setSaved(null), 2000);
    } finally {
      setSaving(null);
    }
  };

  const reset = async (key: string, defaultValue: string) => {
    setSaving(key);
    try {
      await fetch(`/api/admin/prompts/${key}/reset`, { method: "DELETE", credentials: "include" });
      setValues((v) => ({ ...v, [key]: defaultValue }));
      setSaved(key);
      setTimeout(() => setSaved(null), 2000);
    } finally {
      setSaving(null);
    }
  };

  if (loading) return <Spinner className="flex justify-center py-12" />;

  return (
    <div className="space-y-5">
      {prompts.map((p) => (
        <div
          key={p.key}
          className={`rounded-xl border p-5 space-y-3 ${p.editable ? "border-border-soft bg-background" : "border-border-soft bg-surface"}`}
        >
          <div className="flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium text-foreground">{p.label}</p>
                {!p.editable && (
                  <span className="inline-flex items-center gap-1 text-xs text-muted-soft bg-surface-dim px-2 py-0.5 rounded-full">
                    <svg className="w-3 h-3" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M12 6h-1V4a3 3 0 0 0-6 0v2H4a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1zm-5 5.73V13h2v-1.27a1.5 1.5 0 1 0-2 0zM7 4a1 1 0 0 1 2 0v2H7V4z" />
                    </svg>
                    {t("prompts.readonly")}
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-soft mt-0.5">{p.description}</p>
            </div>
          </div>
          <textarea
            value={p.editable ? (values[p.key] ?? p.current_value) : p.current_value}
            onChange={p.editable ? (e) => setValues((v) => ({ ...v, [p.key]: e.target.value })) : undefined}
            readOnly={!p.editable}
            rows={14}
            spellCheck={false}
            className={`w-full text-xs font-mono rounded-lg border px-3 py-2.5 resize-y leading-relaxed focus:outline-none ${
              p.editable
                ? "border-border bg-background text-foreground focus:ring-2 focus:ring-kb"
                : "border-border-soft bg-surface text-muted-soft cursor-not-allowed select-none"
            }`}
          />
          {p.editable && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => save(p.key)}
                disabled={saving === p.key}
                className="text-sm btn-primary px-4 py-1.5 rounded-lg  disabled:opacity-50"
              >
                {saving === p.key ? t("saving") : saved === p.key ? t("saved") : t("save")}
              </button>
              <button
                onClick={() => reset(p.key, p.default_value)}
                disabled={saving === p.key || values[p.key] === p.default_value}
                className="text-sm text-muted hover:text-foreground-soft px-3 py-1.5 rounded-lg border border-border hover:bg-surface disabled:opacity-40"
              >
                {t("reset")}
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
