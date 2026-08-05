"use client";

/**
 * Ein Grammatikthema anlegen.
 *
 * Der Dozent tippt zwei Woerter, etwa "Konjunktiv II". Kein Prompt, keine
 * Anweisung. Die KI arbeitet daraus Regel und Musterpaar aus, und er bekommt
 * genau das Musterpaar zu sehen, bevor irgendetwas gespeichert wird.
 *
 * Dieser Blick ist nicht Komfort, sondern die einzige Pruefstelle. Die
 * Grammatik-Uebung ist das einzige Werkzeug, das nicht aus den Quellen antwortet:
 * das Thema kommt vom Dozenten, die Grammatik aus dem Modell, die Quellen liefern
 * nur den Wortschatz. Damit faellt die Quellen-Grenze als Netz gegen einen Irrtum
 * weg, und ein falsches Muster wuerde ein ganzer Kurs mituebe.
 *
 * Die erzeugte Regel bekommt er nie zu sehen. Eine Sprachlehrkraft soll keine
 * Modell-Anweisungen formulieren muessen, sie arbeitet mit Beispielen.
 */

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowClockwise, Sparkle } from "@phosphor-icons/react";

import { exampleSlots, usablePairs, type ExamplePair } from "./_grammarTopics";

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

  function setPair(index: number, part: "before" | "after", value: string) {
    const rows = exampleSlots(pairs);
    rows[index] = { ...rows[index], [part]: value };
    setPairs(rows);
  }

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

      {previewed && (
        <>
          <p className="text-3xs mt-1" style={{ color: "var(--muted)" }}>
            {t("grammarTopics.checkHint")}
          </p>
          {exampleSlots(pairs).map((pair, i) => (
            <div key={i} className="flex flex-col gap-1">
              <input
                value={pair.before}
                onChange={(e) => setPair(i, "before", e.target.value)}
                placeholder={t("grammarTopics.beforePlaceholder")}
                className={field}
                style={fieldStyle}
              />
              <input
                value={pair.after}
                onChange={(e) => setPair(i, "after", e.target.value)}
                placeholder={t("grammarTopics.afterPlaceholder")}
                className={field}
                style={fieldStyle}
              />
            </div>
          ))}
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
