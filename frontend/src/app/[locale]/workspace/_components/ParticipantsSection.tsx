"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";

interface Participant {
  user_id: number;
  display_name: string;
  username: string;
  role: "student" | "tutor";
  joined_at: string | null;
  enrolled_until: string | null;
}

interface Props {
  workspaceUuid: string;
  /** Called after a promotion or demotion, so a list outside can update its icon. */
  onRolesChanged?: () => void;
}

/**
 * Who is in the course and who is a tutor, with the promotion prompt.
 *
 * Fetches its own data, so both places can drop it in: the modal on the module
 * list and the sharing window inside a module. Whether promoting is offered at
 * all comes from the backend, not from the caller.
 */
export default function ParticipantsSection({ workspaceUuid, onRolesChanged }: Props) {
  const t = useTranslations("workspace.list");
  const locale = useLocale();
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [canEdit, setCanEdit] = useState(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [busyUser, setBusyUser] = useState<number | null>(null);
  const [confirmUser, setConfirmUser] = useState<Participant | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/participants`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setParticipants(data.participants);
      setCanEdit(data.can_edit);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [workspaceUuid]);

  useEffect(() => { load(); }, [load]);

  async function setRole(p: Participant, role: "student" | "tutor") {
    setBusyUser(p.user_id);
    try {
      const res = await fetch(
        `/api/ai-assistant/workspaces/${workspaceUuid}/participants/${p.user_id}`,
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role }),
        },
      );
      if (res.ok) {
        setParticipants((prev) =>
          prev.map((x) => x.user_id === p.user_id ? { ...x, role } : x),
        );
        onRolesChanged?.();
      }
    } catch {
      /* ignore */
    } finally {
      setBusyUser(null);
      setConfirmUser(null);
    }
  }

  const formatDate = (iso: string | null) =>
    iso
      ? new Date(iso).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", {
          day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin",
        })
      : null;

  return (
    <>
      <p className="text-sm mb-5" style={{ color: "var(--muted)" }}>
        {canEdit ? t("participantsHint") : t("participantsReadonlyHint")}
      </p>

      {loading ? (
        <div className="flex items-center justify-center py-10">
          <Spinner size="md" />
        </div>
      ) : failed ? (
        <p className="text-sm py-6 text-center" style={{ color: "var(--error)" }}>
          {t("participantsLoadFailed")}
        </p>
      ) : participants.length === 0 ? (
        <p className="text-sm py-6 text-center" style={{ color: "var(--muted)" }}>
          {t("participantsEmpty")}
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-border-soft border border-border-soft rounded-lg overflow-hidden">
          {participants.map((p) => (
            <li key={p.user_id} className="flex items-center gap-3 px-4 py-3 bg-background">
              <div className="min-w-0 flex-1">
                <span className="block text-sm font-medium truncate">{p.display_name}</span>
                <span className="block text-xs truncate" style={{ color: "var(--muted)" }}>
                  {p.username}
                  {formatDate(p.enrolled_until) && `, ${t("untilDate", { date: formatDate(p.enrolled_until)! })}`}
                </span>
              </div>

              {p.role === "tutor" && (
                <span
                  className="text-2xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap"
                  style={{ backgroundColor: "var(--kb)", color: "#fff" }}
                >
                  {t("roleTutor")}
                </span>
              )}

              {canEdit && (
                <button
                  type="button"
                  disabled={busyUser === p.user_id}
                  onClick={() =>
                    p.role === "tutor" ? setRole(p, "student") : setConfirmUser(p)
                  }
                  className="text-xs font-medium whitespace-nowrap hover:underline disabled:opacity-50"
                  style={{ color: p.role === "tutor" ? "var(--error)" : "var(--kb)" }}
                >
                  {busyUser === p.user_id
                    ? "…"
                    : p.role === "tutor" ? t("demoteToStudent") : t("promoteToTutor")}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Promotion hands over full rights, so it is worth one deliberate click. */}
      {confirmUser && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
          onClick={(e) => { if (e.target === e.currentTarget) setConfirmUser(null); }}
        >
          <div className="w-full max-w-sm rounded-xl p-6 shadow-xl" style={{ backgroundColor: "var(--surface)" }}>
            <h3 className="text-base font-semibold mb-2">
              {t("promoteConfirmTitle", { name: confirmUser.display_name })}
            </h3>
            <p className="text-sm mb-5" style={{ color: "var(--muted)" }}>
              {t("promoteConfirmBody")}
            </p>
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={() => setConfirmUser(null)}
                className="btn-cancel px-4 py-2 rounded-lg text-sm font-medium"
                style={{ backgroundColor: "var(--border)", color: "var(--foreground)" }}
              >
                {t("cancel")}
              </button>
              <button
                type="button"
                onClick={() => setRole(confirmUser, "tutor")}
                className="btn-primary px-4 py-2 rounded-lg text-sm font-medium"
              >
                {t("promoteToTutor")}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
