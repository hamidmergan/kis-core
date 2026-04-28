"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CalendarBlank } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import ExpandableText from "@/components/ui/ExpandableText";
import UpcomingDeadlinesWidget from "./UpcomingDeadlinesWidget";
import type { StudentModule } from "../_shared";

export default function StudentView() {
  const searchParams = useSearchParams();
  const [modules, setModules] = useState<StudentModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrollCode, setEnrollCode] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [enrollError, setEnrollError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    if (code) setEnrollCode(code);
  }, [searchParams]);

  const loadModules = useCallback(async () => {
    try {
      const res = await fetch("/api/ki-assistent/my-modules", { credentials: "include" });
      if (res.ok) setModules(await res.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadModules().finally(() => setLoading(false));
  }, [loadModules]);

  useEffect(() => {
    const needsPoll = modules.some((m) => m.status === "pending" || m.status === "indexing");
    if (!needsPoll) return;
    const id = setInterval(loadModules, 3000);
    return () => clearInterval(id);
  }, [modules, loadModules]);

  async function handleEnroll(e: React.FormEvent) {
    e.preventDefault();
    if (!enrollCode.trim()) return;
    setEnrolling(true);
    setEnrollError(null);
    try {
      const res = await fetch("/api/ki-assistent/enroll", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enroll_code: enrollCode.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Ungültiger Code");
      }
      setEnrollCode("");
      await loadModules();
    } catch (err: unknown) {
      setEnrollError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setEnrolling(false);
    }
  }

  return (
    <div className="px-4 sm:px-6 md:px-8 pt-10 pb-20 lg:pt-15 lg:pb-30">
      <div className="max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold mb-10">Willkommen bei KIS</h1>

      <div className="mb-12">
        <UpcomingDeadlinesWidget />
      </div>

      <h2 className="text-xl font-semibold mb-8">Meine Workspaces</h2>

      <section
        className="rounded-xl p-5 mb-8"
        style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
      >
        <p className="text-sm font-medium mb-3" style={{ color: "var(--text)" }}>
          Einschreibecode eingeben
        </p>
        <form onSubmit={handleEnroll} className="flex gap-2">
          <input
            type="text"
            value={enrollCode}
            onChange={(e) => {
              setEnrollCode(e.target.value);
              setEnrollError(null);
            }}
            placeholder="z. B. a1b2c3d4"
            className="flex-1 rounded-lg border px-3 py-2 text-sm focus:outline-none font-mono"
            style={{
              backgroundColor: "var(--bg)",
              borderColor: enrollError ? "#E11D48" : "var(--border)",
              color: "var(--text)",
            }}
          />
          <button
            type="submit"
            disabled={enrolling || !enrollCode.trim()}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 whitespace-nowrap bg-primary"
          >
            {enrolling ? "…" : "Einschreiben"}
          </button>
        </form>
        {enrollError && (
          <p className="mt-2 text-sm" style={{ color: "#E11D48" }}>
            {enrollError}
          </p>
        )}
      </section>

      {loading ? (
        <div className="flex items-center justify-center min-h-[60vh]">
          <Spinner size="lg" />
        </div>
      ) : modules.length === 0 ? (
        <p className="text-center py-10 text-sm" style={{ color: "var(--muted)" }}>
          Du bist noch in keinem Workspace eingeschrieben.
        </p>
      ) : (
        <ul className="divide-y divide-gray-100 border border-gray-200 rounded-xl overflow-hidden">
          {modules.map((m, i) => {
            const href = m.enrollment_id ? `/workspaces/${m.uuid}?eid=${m.enrollment_id}` : `/workspaces/${m.uuid}`;
            const untilDate = m.enrolled_until
              ? new Date(m.enrolled_until).toLocaleDateString("de-DE", {
                  day: "2-digit",
                  month: "2-digit",
                  year: "numeric",
                  timeZone: "Europe/Berlin",
                })
              : null;
            return (
              <li key={`${m.uuid}-${m.enrollment_id ?? i}`} className="px-5 py-4 bg-white hover:bg-gray-100">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium truncate">{m.title}</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      {m.description && (
                        <ExpandableText className="text-xs text-gray-400" clampClass="line-clamp-1">
                          {m.description}
                        </ExpandableText>
                      )}
                      {untilDate && (
                        <span className="inline-flex items-center gap-1 text-xs text-gray-400 whitespace-nowrap">
                          <CalendarBlank size={12} />
                          bis {untilDate}
                        </span>
                      )}
                    </div>
                  </div>
                  <Link
                    href={href}
                    className="flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-primary"
                  >
                    Öffnen
                  </Link>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      </div>
    </div>
  );
}
