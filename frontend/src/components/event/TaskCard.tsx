"use client";

import { Check, Gift, Minus } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { TASK_IDS, type TaskId } from "@/lib/event/tasks";

const DEMO_TASKS: ReadonlySet<TaskId> = new Set(["praesentation", "screencast"]);

function taskHref(id: TaskId, workspace: string): string {
  if (id === "question") return workspace ? `/workspace/${encodeURIComponent(workspace)}` : "/workspace";
  return id === "praesentation" ? "/tools/praesentation-demo" : "/tools/screencast-demo";
}

/** Three linked tasks, ticked by the server, with the gift note once all are done. */
export function TaskCard({
  done,
  workspace,
  workspaceTitle,
  onMinimize,
}: {
  done: Partial<Record<TaskId, number>>;
  workspace: string;
  workspaceTitle: string;
  onMinimize: () => void;
}) {
  const t = useTranslations("eventTasks");
  const count = TASK_IDS.filter((id) => done[id]).length;

  return (
    <section className="w-full rounded-2xl border-2 border-kb-dark bg-background p-5" data-testid="event-task-card">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mb-1">
        <Gift size={26} weight="regular" className="text-kb-dark shrink-0" aria-hidden />
        <h2 className="text-lg font-semibold flex-1 min-w-0">{t("title")}</h2>
        {/* On a phone the progress drops below the title so the title keeps one line. */}
        <span className="text-sm text-muted whitespace-nowrap order-last basis-full pl-9.5 sm:order-none sm:basis-auto sm:pl-0">
          {t("progress", { n: count, total: TASK_IDS.length })}
        </span>
        <button
          type="button"
          onClick={onMinimize}
          aria-label={t("minimize")}
          title={t("minimize")}
          className="shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-lg border-2 border-border-soft text-muted hover:border-kb focus-visible:border-kb transition-colors"
        >
          <Minus size={16} weight="bold" />
        </button>
      </div>
      <p className="text-sm text-foreground-soft mb-4">{t("intro")}</p>
      <div className="grid gap-3 md:grid-cols-3">
        {TASK_IDS.map((id) => {
          const ticked = Boolean(done[id]);
          return (
            <Link
              key={id}
              href={taskHref(id, workspace)}
              className="flex gap-3 items-start rounded-xl border-2 border-border-soft hover:border-kb focus-visible:border-kb transition-colors p-3.5 no-underline text-foreground"
              data-testid={`event-task-${id}`}
              data-done={ticked ? "1" : "0"}
            >
              <span
                className={`shrink-0 mt-0.5 w-5 h-5 rounded-md border-2 flex items-center justify-center ${
                  ticked ? "border-[var(--kb)] bg-[var(--kb)]" : "border-[var(--border)] bg-background"
                }`}
                style={{ color: "#fff" }}
                role="img"
                aria-label={ticked ? t("doneAria") : t("openAria")}
              >
                {ticked && <Check size={11} weight="bold" />}
              </span>
              <span className="flex-1 min-w-0">
                <span className={`block text-base font-semibold ${ticked ? "text-foreground-soft" : ""}`}>
                  {t(`tasks.${id}.title`)}
                  {DEMO_TASKS.has(id) && (
                    <span className="ml-1.5 align-[2px] text-xs font-semibold text-kb-dark border-2 border-kb-dark rounded-md px-1.5">
                      {t("demo")}
                    </span>
                  )}
                </span>
                <span className="block text-sm text-foreground-soft mt-0.5">
                  {id !== "question"
                    ? t(`tasks.${id}.body`)
                    : workspaceTitle
                      ? t("tasks.question.body", { title: workspaceTitle })
                      : t("tasks.question.bodyNoTitle")}
                </span>
              </span>
            </Link>
          );
        })}
      </div>
      {count === TASK_IDS.length && (
        <div className="mt-4 flex items-center gap-3.5 rounded-xl bg-kb text-on-accent p-3.5" data-testid="event-task-finish">
          <Gift size={32} weight="regular" className="shrink-0" aria-hidden />
          <p className="text-base">
            <strong>{t("finishTitle")}</strong> {t("finishText")}
          </p>
        </div>
      )}
    </section>
  );
}

/** The folded card: gift, label and one dot per task, filled once everything is done. */
export function TaskGiftButton({ done, onOpen }: { done: Partial<Record<TaskId, number>>; onOpen: () => void }) {
  const t = useTranslations("eventTasks");
  const complete = TASK_IDS.every((id) => done[id]);
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={complete ? t("buttonDone") : t("button")}
      className={`shrink-0 inline-flex items-center gap-2.5 rounded-xl border-2 px-2.5 sm:px-3.5 py-2 text-base font-semibold whitespace-nowrap transition-colors ${
        complete
          ? "bg-kb border-kb text-on-accent hover:border-kb-dark"
          : "bg-background border-kb-dark text-kb-dark hover:border-kb"
      }`}
      data-testid="event-task-button"
    >
      <Gift size={22} weight="regular" aria-hidden />
      <span className="hidden sm:inline">{complete ? t("buttonDone") : t("button")}</span>
      <span className="inline-flex gap-1" aria-hidden>
        {TASK_IDS.map((id) => (
          <i key={id} className={`block w-2 h-2 rounded-full border-2 border-current ${done[id] ? "bg-current" : ""}`} />
        ))}
      </span>
    </button>
  );
}
