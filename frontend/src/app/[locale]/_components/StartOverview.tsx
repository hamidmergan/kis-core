"use client";

import { useLocale, useTranslations } from "next-intl";
import { AIA_AUDIENCE, TOOLS_AUDIENCE, type Audience, type HomeTarget } from "@/lib/modules";
import { TOOL_ICONS } from "@/lib/toolIcons";
import { Greeting } from "@/app/[locale]/workspace/_components/Greeting";
import { EvaluationInvite } from "@/app/[locale]/workspace/_components/EvaluationInvite";
import HoverTooltip from "@/components/ui/HoverTooltip";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import { ROUTES } from "@/lib/event/routes";
import { EVENT_ICONS } from "@/lib/event/icons";
import { useText2 } from "@/lib/event/useText2";
import type { Text2 } from "@/lib/event/types";
import { StartTile } from "./StartTile";

type ToolTarget = Extract<HomeTarget, { kind: "tool" }>;

/** Who a group addresses, shown once next to its heading. Each tag has its own hover explanation. */
function AudienceTags({ tags }: { tags: { label: string; hint: string }[] }) {
  return (
    <span className="flex gap-1">
      {tags.map((tag) => (
        <HoverTooltip key={tag.label} text={tag.hint} tapToOpen>
          <span
            className="text-2xs font-medium px-1.5 py-0.5 rounded-full border border-border-soft"
            style={{ backgroundColor: "var(--badge-slate-bg)", color: "var(--badge-slate-fg)" }}
          >
            {tag.label}
          </span>
        </HoverTooltip>
      ))}
    </span>
  );
}

/** The start page for everyone with more than one place to go: the assistant first, then every tool. */
export default function StartOverview({
  firstName,
  targets,
  stamp = null,
  stampFrom = "",
  stampTitle,
  stampBody,
}: {
  firstName: string;
  targets: HomeTarget[];
  stamp?: "open" | "upcoming" | null;
  stampFrom?: string;
  stampTitle?: Text2;
  stampBody?: Text2;
}) {
  const t = useTranslations("startOverview");
  const text = useText2();
  const locale = useLocale();
  const day = stampFrom ? new Date(`${stampFrom}T12:00:00`) : null;
  const stampNote =
    day && !Number.isNaN(day.getTime())
      ? t("stamp.from", { date: day.toLocaleDateString(locale === "en" ? "en-GB" : "de-DE", { day: "numeric", month: "long", year: "numeric" }) })
      : t("stamp.soon");
  const { variant: mascotVariant } = useMascotPref();
  const aia = targets.find((z) => z.kind === "aia");
  // The campus assistant addresses everyone, so it sits beside the assistant instead of among the teaching tools.
  const campus = targets.find((z): z is ToolTarget => z.kind === "tool" && z.key === "campus");
  const tools = targets.filter((z): z is ToolTarget => z.kind === "tool" && z.key !== "campus");
  const headingClass = "text-sm font-semibold uppercase tracking-wider";
  const gridClass = "grid gap-4 sm:grid-cols-2 lg:grid-cols-3";
  const audienceTags = (audience: readonly Audience[]) =>
    audience.map((a) => ({ label: t(`audience.${a}`), hint: t(`audienceHint.${a}`) }));

  return (
    <div className="page-shell pt-6 pb-20 lg:pt-15 lg:pb-30">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col gap-8" data-testid="start-overview">
          {/* Same columns as the tiles below, so the assistant keeps their width. */}
          <div className={gridClass}>
            <div className="sm:col-span-2">
              <Greeting firstName={firstName} />
            </div>
            {/* Right after the greeting in the source so the invite tops the single column on a phone, wide screens move it below the tiles. */}
            <div className="flex flex-col md:flex-row gap-4 empty:hidden sm:col-span-2 lg:col-span-3 sm:order-last sm:mt-4">
              <EvaluationInvite />
            </div>
            {/* Before the assistant in the source so it follows on a phone, the grid keeps it in the third column on wide screens. */}
            {stamp && (
              <section className="flex flex-col gap-2 lg:col-start-3 lg:row-start-2">
                <h2 className={headingClass}>{t("groups.event")}</h2>
                <StartTile
                  href={stamp === "open" ? ROUTES.stamp : undefined}
                  note={stamp === "upcoming" ? stampNote : undefined}
                  icon={EVENT_ICONS.star}
                  title={stampTitle ? text(stampTitle) : t("stamp.title")}
                  body={stampBody ? text(stampBody) : t("stamp.body")}
                  testId="start-tile-stamp"
                />
              </section>
            )}
            {aia && (
              <section className="flex flex-col gap-2 lg:col-start-1 lg:row-start-2">
                <div className="flex items-center gap-2">
                  <h2 className={headingClass}>{t("groups.aia")}</h2>
                  <AudienceTags tags={audienceTags(AIA_AUDIENCE)} />
                </div>
                <StartTile
                  href={aia.href}
                  avatar={<Mascot variant={mascotVariant} size={52} state="idle" />}
                  title={t("aia.title")}
                  body={t("aia.body")}
                  testId="start-tile-aia"
                />
              </section>
            )}
            {campus && (
              <section className="flex flex-col gap-2 lg:col-start-2 lg:row-start-2">
                <h2 className={headingClass}>{t("groups.campus")}</h2>
                <StartTile
                  href={campus.href}
                  icon={TOOL_ICONS[campus.key]}
                  title={t("tools.campus.title")}
                  body={t("tools.campus.body")}
                  testId="start-tile-campus"
                />
              </section>
            )}
          </div>

          {tools.length > 0 && (
            <section className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <h2 className={headingClass}>{t("groups.tools")}</h2>
                <AudienceTags tags={audienceTags(TOOLS_AUDIENCE)} />
              </div>
              <div className={gridClass}>
                {tools.map((z) => (
                  <StartTile
                    key={z.key}
                    href={z.href}
                    icon={TOOL_ICONS[z.key]}
                    title={t(`tools.${z.key}.title`)}
                    body={t(`tools.${z.key}.body`)}
                    testId={`start-tile-${z.key}`}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
