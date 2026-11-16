"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { usePathname } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { Stack } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { useNavTransition } from "@/components/ui/useNavTransition";
import { EmptyState } from "@/components/ui/EmptyState";
import { JOBS_STATUS_CHANGED_EVENT } from "@/lib/jobs-events";
import { readPrefs, updatePrefs } from "@/lib/browserStore";
import type { MyJob } from "./_myJob";
import { hasUnseenDone } from "./_unseen";
import JobsPanelRow from "./JobsPanelRow";
import { useMyJobs } from "./useMyJobs";

export default function JobsPanel() {
  const tHeader = useTranslations("header");
  const tJobs = useTranslations("myJobs");
  const tPanel = useTranslations("myJobs.panel");

  const [open, setOpen] = useState(false);
  const jobs = useMyJobs();
  const [lastSeen, setLastSeen] = useState<number | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const router = useRouter();
  const { pending: toJobsPending, navigate } = useNavTransition();
  // The button leads to /my-jobs, so it also shows when you are already there.
  const onJobsPage = usePathname().startsWith("/my-jobs");

  // Remembers the last look so the dot only reports what is new.
  useEffect(() => {
    const stored = Number(readPrefs().jobsLastSeen);
    if (stored > 0) { setLastSeen(stored); return; }
    const now = Date.now();
    updatePrefs({ jobsLastSeen: now });
    setLastSeen(now);
  }, []);

  // Opening marks everything seen, closing catches what finished meanwhile.
  useEffect(() => {
    if (!open) return;
    const markSeen = () => {
      const now = Date.now();
      updatePrefs({ jobsLastSeen: now });
      setLastSeen(now);
    };
    markSeen();
    return markSeen;
  }, [open]);

  // Close on outside click/tap
  useEffect(() => {
    if (!open) return;
    const handler = (e: PointerEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [open]);

  const handleMouseEnter = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    setOpen(true);
  };

  const handleMouseLeave = () => {
    hoverTimeoutRef.current = setTimeout(() => setOpen(false), 150);
  };

  useEffect(() => () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
  }, []);

  const openJobsPage = () => {
    setOpen(false);
    navigate(() => router.push("/my-jobs"));
  };

  const handleButtonClick = () => {
    if (open) openJobsPage();
    else setOpen(true);
  };

  const hasFreshResult = lastSeen !== null && hasUnseenDone(jobs, lastSeen);

  const handleRetry = async (e: React.MouseEvent, job: MyJob) => {
    e.stopPropagation();
    setRetrying(job.job_uuid);
    try {
      const res = await fetch(`/api/jobs/${job.job_uuid}/retry`, { method: "POST", credentials: "include" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || tJobs("retryFailed"));
        return;
      }
      window.dispatchEvent(new Event(JOBS_STATUS_CHANGED_EVENT));
      openJobsPage();
    } finally {
      setRetrying(null);
    }
  };

  return (
    <div className="relative" ref={panelRef} onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave}>
      <button
        onClick={handleButtonClick}
        onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open("/my-jobs", "_blank"); } }}
        aria-label={tHeader("jobs")}
        title={tHeader("jobs")}
        aria-current={onJobsPage ? "page" : undefined}
        className={`relative flex items-center justify-center w-10 h-10 sm:w-auto sm:h-9 sm:px-3 sm:gap-1.5 rounded-full btn-on-dark${onJobsPage ? " is-active" : ""}`}
        data-tour="jobs-entry"
      >
        {toJobsPending ? <Spinner size="sm" color="current" /> : <Stack size={17} weight="bold" aria-hidden="true" />}
        <span className="hidden sm:inline text-sm font-medium">{tHeader("jobs")}</span>
        {hasFreshResult && (
          <>
            <span className="absolute top-0 right-0 w-1.5 h-1.5 bg-error rounded-full shadow" aria-hidden="true" />
            <span className="sr-only">{tPanel("newResults")}</span>
          </>
        )}
      </button>

      {/* Mobile backdrop */}
      {open && <div className="sm:hidden fixed inset-0 bg-black/40 z-40" onClick={() => setOpen(false)} />}
      {open && (
        <div className="
          fixed inset-x-0 bottom-0 z-50 rounded-t-xl
          sm:absolute sm:inset-auto sm:right-0 sm:top-full sm:bottom-auto sm:mt-2 sm:w-80 sm:rounded-xl
          shadow-xl overflow-hidden
        " style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)" }}>
          <div className="px-4 py-3 border-b border-border-soft flex items-center justify-between">
            <span className="text-sm font-semibold text-foreground">{tJobs("title")}</span>
          </div>

          <div className="px-4 py-2 border-b" style={{ borderColor: "var(--border)" }}>
            <p className="text-xs text-kb">
              {tPanel("notice")}
            </p>
          </div>

          <div>
            {jobs.length === 0 ? (
              <EmptyState
                icon={<Stack size={32} weight="bold" />}
                text={tPanel("empty")}
              />
            ) : (
              <ul className="divide-y divide-border-soft">
                {jobs.slice(0, 3).map((job) => (
                  <JobsPanelRow
                    key={job.job_uuid}
                    job={job}
                    retrying={retrying === job.job_uuid}
                    onRetry={handleRetry}
                    onOpen={openJobsPage}
                    onClose={() => setOpen(false)}
                  />
                ))}
              </ul>
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-border-soft text-center">
            <Link
              href="/my-jobs"
              onClick={() => setOpen(false)}
              className="text-xs text-kb hover:underline"
            >
              {tPanel("viewAll")}
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
