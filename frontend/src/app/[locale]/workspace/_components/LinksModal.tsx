"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import LinkRow from "./LinkRow";
import { MAX_ACCESS_LINKS, type AccessLink } from "../_shared";

interface LinksModalProps {
  workspaceUuid: string;
  links: AccessLink[];
  onClose: () => void;
  onCreated: (link: AccessLink) => void;
  onRequestDelete: (link: AccessLink) => void;
}

/** One window for the enrollment links of a workspace: see them, copy them,
 *  delete them, and create a new one without a second dialog on top. */
export default function LinksModal({
  workspaceUuid,
  links,
  onClose,
  onCreated,
  onRequestDelete,
}: LinksModalProps) {
  const t = useTranslations("workspace.list");
  const [expiresAt, setExpiresAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      onCreated(data);
      setExpiresAt("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("unknownError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={t("linksTitle")} size="md">
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
            <LinkRow key={link.id} link={link} onRequestDelete={onRequestDelete} />
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
    </Modal>
  );
}
