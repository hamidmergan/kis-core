"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

interface CustomRole {
  id?: number;
  name: string;
  allow_aia: boolean;
  allowed_tools: string[];
}

interface Props {
  initial: CustomRole | null;
  availableTools: string[];
  onClose: () => void;
  onSaved: () => void;
}

export default function RoleBuilderDialog({ initial, availableTools, onClose, onSaved }: Props) {
  const t = useTranslations("admin.roles");
  const [name, setName] = useState(initial?.name ?? "");
  const [allowAia, setAllowAia] = useState(initial?.allow_aia ?? false);
  const [tools, setTools] = useState<Set<string>>(new Set(initial?.allowed_tools ?? []));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleTool(key: string) {
    const next = new Set(tools);
    if (next.has(key)) next.delete(key); else next.add(key);
    setTools(next);
  }

  async function save() {
    setSaving(true);
    setError(null);
    const payload = { name: name.trim(), allow_aia: allowAia, allowed_tools: Array.from(tools) };
    const url = initial?.id ? `/api/admin/roles/${initial.id}` : `/api/admin/roles`;
    const method = initial?.id ? "PUT" : "POST";
    try {
      const res = await fetch(url, {
        method,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0, 0, 0, 0.5)" }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-md rounded-xl p-6 space-y-4"
        style={{ background: "var(--background)", border: "1px solid var(--border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold">{initial?.id ? t("edit") : t("newRole")}</h3>

        <label className="block">
          <span className="text-sm font-medium">{t("name")}</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-kb"
            style={{ borderColor: "var(--border)", background: "var(--surface)" }}
          />
        </label>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={allowAia}
            onChange={(e) => setAllowAia(e.target.checked)}
          />
          <span className="text-sm">{t("allowAia")}</span>
        </label>

        <fieldset>
          <legend className="text-sm font-medium mb-2">{t("tools")}</legend>
          <div className="flex flex-col gap-1">
            {availableTools.map((key) => (
              <label key={key} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={tools.has(key)}
                  onChange={() => toggleTool(key)}
                />
                <span>{key}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {error && (
          <p className="text-sm" style={{ color: "var(--error)" }}>{error}</p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-md text-sm border border-border hover:bg-surface-dim"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving || !name.trim()}
            className="px-4 py-2 rounded-md text-sm font-medium btn-primary disabled:opacity-50"
          >
            {t("save")}
          </button>
        </div>
      </div>
    </div>
  );
}
