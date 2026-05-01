"use client";

import { useEffect, useState } from "react";
import Spinner from "@/components/ui/Spinner";

interface ToolEntry {
  key: string;
  label: string;
  enabled: boolean;
}

export default function ToolsTab() {
  const [tools, setTools] = useState<ToolEntry[] | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/tools", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setTools(d.tools ?? []));
  }, []);

  const toggle = async (key: string, enabled: boolean) => {
    setSaving(key);
    setTools((prev) => prev?.map((t) => (t.key === key ? { ...t, enabled } : t)) ?? null);
    try {
      await fetch(`/api/admin/tools/${key}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
    } finally {
      setSaving(null);
    }
  };

  if (!tools) return <Spinner className="flex justify-center py-12" />;

  return (
    <div className="border border-border-soft rounded-xl bg-white p-5">
      <p className="text-sm font-medium text-foreground mb-1">Tools ein-/ausschalten</p>
      <p className="text-xs text-muted mb-4">Deaktivierte Tools werden auf der Startseite ausgeblendet.</p>
      <div className="space-y-3">
        {tools.map((tool) => (
          <div key={tool.key} className="flex items-center justify-between">
            <span className="text-sm text-foreground-soft">{tool.label}</span>
            <button
              onClick={() => toggle(tool.key, !tool.enabled)}
              disabled={saving === tool.key}
              className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-kb ${
                tool.enabled ? "bg-kb" : "bg-border"
              } disabled:opacity-50`}
              aria-label={`${tool.label} ${tool.enabled ? "deaktivieren" : "aktivieren"}`}
            >
              <span
                className={`pointer-events-none inline-block w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
                  tool.enabled ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
