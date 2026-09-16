"use client";

import { useTranslations } from "next-intl";
import { ChatCircleDots, Presentation } from "@phosphor-icons/react";
import { AIA_AUDIENCE, TOOLS_AUDIENCE, type Audience, type HomeTarget } from "@/lib/modules";
import { TOOL_ICONS } from "@/lib/toolIcons";
import { Greeting } from "@/app/[locale]/workspace/_components/Greeting";
import { EvaluationInvite } from "@/app/[locale]/workspace/_components/EvaluationInvite";
import HoverTooltip from "@/components/ui/HoverTooltip";
import { StartTile } from "./StartTile";

/** Announced tools without a route yet. Not permission keys, so they live here and not in TOOL_ROUTES. */
const COMING_TOOLS = [{ key: "slides", icon: Presentation }] as const;

type ToolTarget = Extract<HomeTarget, { kind: "tool" }>;

/** Who a group addresses, shown once next to its heading. Each tag has its own hover explanation. */
function AudienceTags({ tags }: { tags: { label: string; hint: string }[] }) {
  return (
    <span className="flex gap-1">
      {tags.map((tag) => (
        <HoverTooltip key={tag.label} text={tag.hint}>
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
export default function StartOverview({ firstName, targets }: { firstName: string; targets: HomeTarget[] }) {
  const t = useTranslations("startOverview");
  const aia = targets.find((z) => z.kind === "aia");
  const tools = targets.filter((z): z is ToolTarget => z.kind === "tool");
  const headingClass = "text-sm font-semibold uppercase tracking-wider";
  const gridClass = "grid gap-4 sm:grid-cols-2 lg:grid-cols-3";
  const audienceTags = (audience: readonly Audience[]) =>
    audience.map((a) => ({ label: t(`audience.${a}`), hint: t(`audienceHint.${a}`) }));

  return (
    <div className="page-shell pt-6 pb-20 lg:pt-15 lg:pb-30">
      <div className="max-w-7xl mx-auto">
        <Greeting firstName={firstName} />

        <div className="flex flex-col md:flex-row gap-4 mb-8 empty:hidden">
          <EvaluationInvite />
        </div>

        <div className="flex flex-col gap-8" data-testid="start-overview">
          {aia && (
            <section className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <h2 className={headingClass}>{t("groups.aia")}</h2>
                <AudienceTags tags={audienceTags(AIA_AUDIENCE)} />
              </div>
              <div className={gridClass}>
                <StartTile
                  href={aia.href}
                  icon={ChatCircleDots}
                  title={t("aia.title")}
                  body={t("aia.body")}
                  testId="start-tile-aia"
                />
              </div>
            </section>
          )}

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
                {COMING_TOOLS.map((c) => (
                  <StartTile
                    key={c.key}
                    icon={c.icon}
                    title={t(`coming.${c.key}.title`)}
                    body={t(`coming.${c.key}.body`)}
                    badge={t("comingBadge")}
                    testId={`start-tile-${c.key}`}
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
