"use client";

/** Create a topic: the teacher sees the pattern pair before anything is saved. */

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowClockwise, Sparkle } from "@phosphor-icons/react";

import {
  editedPair,
  shownSuggestion,
  usablePairs,
  type ExamplePair,
} from "./_grammarTopics";

export function GrammarTopicForm({
  workspaceUuid,
  onSaved,
  onCancel,
}: {
  workspaceUuid: string;
  onSaved: (topic: { id: number; name: string }) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const [name, setName] = useState("");
  const [rule, setRule] = useState("");
  const [suggested, setSuggested] = useState("");
  const [pairs, setPairs] = useState<ExamplePair[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const previewed = Boolean(rule);

  async function preview() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(
        `/api/ai-assistant/workspaces/${workspaceUuid}/grammar-topics/preview`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name.trim() }),
        },
      );
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(data?.detail || t("grammarTopics.failed"));
        return;
      }
      setRule(data.rule);
      setSuggested(data.suggested_name || "");
      setPairs(data.examples || []);
    } catch {
      setError(t("grammarTopics.failed"));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    const examples = usablePairs(pairs);
    if (!examples.length) {
      setError(t("grammarTopics.needExample"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await fetch(
        `/api/ai-assistant/workspaces/${workspaceUuid}/grammar-topics`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name.trim(), rule, examples }),
        },
      );
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(data?.detail || t("grammarTopics.failed"));
        return;
      }
      onSaved(data.topic);
    } catch {
      setError(t("grammarTopics.failed"));
    } finally {
      setBusy(false);
    }
  }

  function setPair(part: "before" | "after", value: string) {
    setPairs([{ ...editedPair(pairs), [part]: value }]);
  }

  // The suggestion only appears when it says something other than what was typed.
  const vorschlag = previewed ? shownSuggestion(name, suggested) : "";

  const field =
    "w-full px-2.5 py-1.5 rounded-lg text-xs bg-transparent text-foreground";
  const fieldStyle = { border: "2px solid var(--border)" };

  return (
    <div className="flex flex-col gap-2">
      <label className="text-3xs" style={{ color: "var(--muted)" }}>
        {t("grammarTopics.nameLabel")}
      </label>
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && name.trim() && !busy && !previewed) preview();
        }}
        placeholder={t("grammarTopics.namePlaceholder")}
        className={field}
        style={fieldStyle}
      />

      {vorschlag && (
        <div className="flex items-center gap-2">
          <p className="text-3xs flex-1" style={{ color: "var(--muted)" }}>
            {t("grammarTopics.understoodAs", { name: vorschlag })}
          </p>
          <button
            type="button"
            onClick={() => setName(vorschlag)}
            className="btn-cancel px-2.5 py-1 rounded-full text-3xs font-semibold whitespace-nowrap"
            style={{
              color: "var(--kb)",
              backgroundColor: "var(--surface)",
              border: "2px solid var(--border)",
            }}
          >
            {t("grammarTopics.useSuggestion")}
          </button>
        </div>
      )}

      {previewed && (
        <>
          <p className="text-3xs mt-1" style={{ color: "var(--muted)" }}>
            {t("grammarTopics.checkHint")}
          </p>
          <div className="flex flex-col gap-1">
            <input
              value={editedPair(pairs).before}
              onChange={(e) => setPair("before", e.target.value)}
              placeholder={t("grammarTopics.beforePlaceholder")}
              className={field}
              style={fieldStyle}
            />
            <input
              value={editedPair(pairs).after}
              onChange={(e) => setPair("after", e.target.value)}
              placeholder={t("grammarTopics.afterPlaceholder")}
              className={field}
              style={fieldStyle}
            />
          </div>
        </>
      )}

      {error && (
        <p className="text-3xs" style={{ color: "#c4820e" }}>
          {error}
        </p>
      )}

      <div className="flex gap-2 mt-1">
        <button
          type="button"
          onClick={onCancel}
          className="btn-cancel px-3 py-1.5 rounded-full text-xs font-semibold"
          style={{
            color: "var(--kb)",
            backgroundColor: "var(--surface)",
            border: "2px solid var(--border)",
          }}
        >
          {t("common.cancel")}
        </button>
        {previewed && (
          <button
            type="button"
            onClick={preview}
            disabled={busy}
            title={t("grammarTopics.again")}
            className="btn-cancel px-3 py-1.5 rounded-full text-xs font-semibold disabled:opacity-50"
            style={{
              color: "var(--kb)",
              backgroundColor: "var(--surface)",
              border: "2px solid var(--border)",
            }}
          >
            <ArrowClockwise size={12} weight="bold" />
          </button>
        )}
        <button
          type="button"
          onClick={previewed ? save : preview}
          disabled={busy || !name.trim()}
          className="btn-fill-accent flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-full text-xs font-semibold disabled:opacity-50"
        >
          <Sparkle size={12} weight="bold" />
          {busy
            ? t("common.loading")
            : previewed
              ? t("grammarTopics.accept")
              : t("grammarTopics.check")}
        </button>
      </div>
    </div>
  );
}
