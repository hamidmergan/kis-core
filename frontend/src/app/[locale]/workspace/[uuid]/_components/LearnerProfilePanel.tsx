"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { levelLabel } from "./language_training/_diagnosis_types";

interface Weakness {
  id: number;
  category: string;
  label: string;
  source_id: number | null;
  effective_weight: number;
  hit_count: number;
  last_seen_at: string;
}

interface Profile {
  enabled: boolean;
  level: string | null;
  level_set_at: string | null;
  weaknesses: Weakness[];
}

// Fixed display order for the known categories (Tasks 4-7); anything unknown
// still renders, just appended after these so nothing silently disappears.
const CATEGORY_ORDER = ["term", "passage", "tool"];

/**
 * The student-facing learner profile: level, tracked weaknesses grouped by
 * category, a tracking on/off switch and an export. Content only (no modal
 * chrome) so it drops into the existing settings Modal.
 *
 * Progress here means the weakness list gets shorter over time (graduation on
 * a correct quiz answer, decay past the admin window), never a higher level:
 * the level only ever comes from a new diagnosis run.
 */
export function LearnerProfilePanel() {
  const t = useTranslations("workspace.detail.learnerProfile");
  const tDiag = useTranslations("workspace.detail.languageTraining.diagnosis");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/ai-assistant/learner-profile", { credentials: "include" });
      if (res.ok) setProfile(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const removeOne = async (id: number) => {
    setBusy(true);
    try {
      await fetch(`/api/ai-assistant/learner-profile/weaknesses/${id}`, {
        method: "DELETE", credentials: "include",
      });
      setProfile((prev) => (prev ? { ...prev, weaknesses: prev.weaknesses.filter((w) => w.id !== id) } : prev));
    } finally {
      setBusy(false);
    }
  };

  const clearAll = async () => {
    if (!window.confirm(t("clearAllConfirm"))) return;
    setBusy(true);
    try {
      await fetch("/api/ai-assistant/learner-profile/weaknesses", {
        method: "DELETE", credentials: "include",
      });
      setProfile((prev) => (prev ? { ...prev, weaknesses: [] } : prev));
    } finally {
      setBusy(false);
    }
  };

  const setEnabled = async (enabled: boolean) => {
    setBusy(true);
    try {
      await fetch("/api/ai-assistant/learner-profile/enabled", {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      setProfile((prev) => (prev ? { ...prev, enabled } : prev));
    } finally {
      setBusy(false);
    }
  };

  const exportMd = () => {
    window.open("/api/ai-assistant/learner-profile/export?fmt=md", "_blank");
  };

  if (!profile) {
    return <p className="text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>;
  }

  const presentCategories = CATEGORY_ORDER.filter((c) => profile.weaknesses.some((w) => w.category === c));
  const otherCategories = Array.from(new Set(profile.weaknesses.map((w) => w.category))).filter(
    (c) => !CATEGORY_ORDER.includes(c),
  );
  const groupOrder = [...presentCategories, ...otherCategories];

  const categoryLabel = (c: string) => {
    if (c === "term") return t("categoryTerm");
    if (c === "passage") return t("categoryPassage");
    if (c === "tool") return t("categoryTool");
    return c;
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("levelLabel")}</p>
          <p className="text-sm mt-0.5" style={{ color: "var(--muted)" }}>
            {profile.level ? levelLabel(profile.level, tDiag("levelAboveB1")) : t("noLevel")}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={profile.enabled}
          aria-label={t("trackingTitle")}
          onClick={() => !busy && setEnabled(!profile.enabled)}
          disabled={busy}
          className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent hover:border-[var(--kb)] disabled:hover:border-transparent transition-colors duration-200"
          style={{ backgroundColor: profile.enabled ? "var(--kb)" : "var(--border)", cursor: busy ? "not-allowed" : "pointer" }}
        >
          <span
            className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
            style={{ transform: profile.enabled ? "translateX(16px)" : "translateX(0)" }}
          />
        </button>
      </div>
      <div>
        <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("trackingTitle")}</p>
        <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>
          {profile.enabled ? t("trackingDescription") : t("trackingOffHint")}
        </p>
      </div>

      <p className="text-xs" style={{ color: "var(--muted)" }}>{t("progressHint")}</p>

      {profile.weaknesses.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--muted)" }}>{t("empty")}</p>
      ) : (
        <>
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            {t("countLine", { n: profile.weaknesses.length })}
          </p>
          <div className="flex flex-col gap-4">
            {groupOrder.map((cat) => (
              <div key={cat}>
                <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
                  {categoryLabel(cat)}
                </p>
                <ul className="mt-1.5 flex flex-col gap-1.5">
                  {profile.weaknesses.filter((w) => w.category === cat).map((w) => (
                    <li
                      key={w.id}
                      className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2"
                      style={{ borderColor: "var(--border)" }}
                    >
                      <span className="text-sm truncate" style={{ color: "var(--foreground)" }}>{w.label}</span>
                      <button
                        type="button"
                        onClick={() => removeOne(w.id)}
                        disabled={busy}
                        className="shrink-0 text-xs px-2.5 py-1 rounded-lg border disabled:opacity-40"
                        style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
                      >
                        {t("knowItAlready")}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="flex flex-wrap items-center gap-2 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
        <button
          type="button"
          onClick={clearAll}
          disabled={busy || profile.weaknesses.length === 0}
          className="text-xs px-3 py-1.5 rounded-lg border disabled:opacity-40"
          style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
        >
          {t("clearAll")}
        </button>
        <button
          type="button"
          onClick={exportMd}
          disabled={busy}
          className="text-xs px-3 py-1.5 rounded-lg border disabled:opacity-40"
          style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
        >
          {t("exportMd")}
        </button>
      </div>
    </div>
  );
}
