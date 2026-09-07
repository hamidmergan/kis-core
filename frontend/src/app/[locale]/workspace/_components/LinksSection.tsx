"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import LinkRow from "./LinkRow";
import { MAX_ACCESS_LINKS, type AccessLink } from "../_shared";

interface LinksSectionProps {
  workspaceUuid: string;
  links: AccessLink[];
  /** Reports the whole new list, so the caller can keep its own copy in step. */
  onLinksChanged: (links: AccessLink[]) => void;
}

/**
 * The enrollment links of a course with their form and their delete prompt.
 *
 * Lives apart from any dialog so both places can show it: the modal on the
 * module list and the sharing window inside a module. The delete prompt sits
 * in here and not in a parent, otherwise every place would build its own.
 */
export default function LinksSection({ workspaceUuid, links, onLinksChanged }: LinksSectionProps) {
  const t = useTranslations("workspace.list");
  const locale = useLocale();
  const [expiresAt, setExpiresAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<AccessLink | null>(null);
  const [deleting, setDeleting] = useState(false);
  const atLimit = links.length >= MAX_ACCESS_LINKS;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/access-links`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        // Empty means the link never expires. Not every course has an end date.
        body: JSON.stringify({ expires_at: expiresAt ? new Date(expiresAt).toISOString() : null }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? t("createError"));
      }
      const data = await res.json();
      onLinksChanged([...links, data]);
      setExpiresAt("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("unknownError"));
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!deleteConfirm) return;
    setDeleting(true);
    try {
      const res = await fetch(
        `/api/ai-assistant/workspaces/${workspaceUuid}/access-links/${deleteConfirm.id}`,
        { method: "DELETE", credentials: "include" },
      );
      if (res.ok) onLinksChanged(links.filter((l) => l.id !== deleteConfirm.id));
    } catch {
      /* Ein fehlgeschlagenes Loeschen laesst den Link stehen, das sagt genug. */
    } finally {
      setDeleting(false);
      setDeleteConfirm(null);
    }
  }

  const expiryLabel = (link: AccessLink) =>
    link.expires_at
      ? t("linkValidUntil", {
          date: new Date(link.expires_at).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", {
            day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin",
          }),
        })
      : t("linkUnlimited");

  return (
    <>
      <p className="text-sm mb-4" style={{ color: "var(--muted)" }}>
        {t("newLinkBody")}
      </p>

      {links.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          {t("noLinks")}
        </p>
      ) : (
        <div className="flex flex-col gap-1">
          {links.map((link) => (
            <LinkRow key={link.id} link={link} onRequestDelete={setDeleteConfirm} />
          ))}
        </div>
      )}

      <div className="mt-5 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
        {atLimit ? (
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            {t("maxLinksReached", { n: MAX_ACCESS_LINKS })}
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: "var(--foreground)" }}>
                {t("validUntilOptionalField")}
              </label>
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <input
                    type="date"
                    value={expiresAt}
                    onChange={(e) => setExpiresAt(e.target.value)}
                    min={new Date().toISOString().split("T")[0]}
                    className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none"
                    style={{ backgroundColor: "var(--background)", borderColor: "var(--border)", color: "var(--foreground)" }}
                  />
                  <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
                    {t("validUntilHint")}
                  </p>
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 whitespace-nowrap"
                >
                  {loading ? t("creating") : t("newLink")}
                </button>
              </div>
            </div>
            {error && (
              <p className="text-sm" style={{ color: "var(--error)" }}>
                {error}
              </p>
            )}
          </form>
        )}
      </div>

      {/* Above the dialog it was opened from, which already sits at z-50. */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-[60] flex items-center justify-center p-4">
          <div className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">{t("deleteLinkTitle")}</h3>
            <p className="text-sm text-foreground-soft mb-1">
              <span className="font-medium">...{deleteConfirm.code}</span> - {expiryLabel(deleteConfirm)}
            </p>
            <p className="text-sm text-error mb-6">{t("deleteLinkWarning")}</p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteConfirm(null)}
                disabled={deleting}
                className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg disabled:opacity-50"
              >
                {t("cancel")}
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50"
              >
                {deleting ? "..." : t("delete")}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
