"use client";

import { useEffect, useState } from "react";
import { notifyWorkspaceLabelsChanged } from "@/hooks/useWorkspaceLabel";

interface Labels {
  singular: string;
  plural: string;
}

const DEFAULTS: Labels = { singular: "Workspace", plural: "Workspaces" };

export default function WorkspaceLabelCard() {
  const [loaded, setLoaded] = useState<Labels | null>(null);
  const [singular, setSingular] = useState("");
  const [plural, setPlural] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const next: Labels = {
          singular: typeof d.workspace_label_singular === "string" && d.workspace_label_singular ? d.workspace_label_singular : DEFAULTS.singular,
          plural: typeof d.workspace_label_plural === "string" && d.workspace_label_plural ? d.workspace_label_plural : DEFAULTS.plural,
        };
        setLoaded(next);
        setSingular(next.singular);
        setPlural(next.plural);
      })
      .catch(() => {
        setLoaded(DEFAULTS);
        setSingular(DEFAULTS.singular);
        setPlural(DEFAULTS.plural);
      });
  }, []);

  if (!loaded) return null;

  const trimmedSingular = singular.trim();
  const trimmedPlural = plural.trim();
  const dirty = trimmedSingular !== loaded.singular || trimmedPlural !== loaded.plural;
  const valid = trimmedSingular.length > 0 && trimmedPlural.length > 0 && trimmedSingular.length <= 40 && trimmedPlural.length <= 40;

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
          workspace_label_singular: trimmedSingular,
          workspace_label_plural: trimmedPlural,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? "Speichern fehlgeschlagen");
      }
      setLoaded({ singular: trimmedSingular, plural: trimmedPlural });
      setSavedAt(Date.now());
      notifyWorkspaceLabelsChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  function reset() {
    setSingular(DEFAULTS.singular);
    setPlural(DEFAULTS.plural);
  }

  const justSaved = savedAt && Date.now() - savedAt < 3000;

  return (
    <div className="border border-border-soft rounded-xl bg-white p-5">
      <p className="text-sm font-medium text-foreground">Bezeichnung &quot;Workspace&quot;</p>
      <p className="text-xs text-muted mt-1 mb-4">
        Wie der Begriff im Frontend angezeigt wird (z. B. &quot;Modul&quot; / &quot;Module&quot; oder &quot;Kurs&quot; / &quot;Kurse&quot;). Default: Workspace / Workspaces.
      </p>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="block">
          <span className="block text-xs text-muted mb-1">Singular</span>
          <input
            type="text"
            value={singular}
            onChange={(e) => setSingular(e.target.value.slice(0, 40))}
            disabled={saving}
            maxLength={40}
            className="w-full text-sm px-3 py-1.5 border-2 border-border rounded-md transition-colors hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50"
          />
        </label>
        <label className="block">
          <span className="block text-xs text-muted mb-1">Plural</span>
          <input
            type="text"
            value={plural}
            onChange={(e) => setPlural(e.target.value.slice(0, 40))}
            disabled={saving}
            maxLength={40}
            className="w-full text-sm px-3 py-1.5 border-2 border-border rounded-md transition-colors hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50"
          />
        </label>
      </div>
      <div className="flex items-center justify-between gap-3 mt-4">
        <button
          type="button"
          onClick={reset}
          disabled={saving || (singular === DEFAULTS.singular && plural === DEFAULTS.plural)}
          className="text-xs text-muted hover:text-kb disabled:opacity-40 disabled:hover:text-muted"
        >
          Zurücksetzen
        </button>
        <div className="flex items-center gap-3">
          {justSaved && !error && <span className="text-xs text-muted">Gespeichert.</span>}
          {error && <span className="text-xs text-error">{error}</span>}
          <button
            type="button"
            onClick={save}
            disabled={saving || !dirty || !valid}
            className="btn-primary px-3 py-1.5 text-xs font-medium rounded-md disabled:opacity-40"
          >
            {saving ? "…" : "Speichern"}
          </button>
        </div>
      </div>
    </div>
  );
}
