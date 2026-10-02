import type { ReactNode } from "react";

const TONES = {
  plain: "bg-background",
  tint: "bg-surface",
  hero: "bg-gradient-to-b from-kb/10 via-kb/5 to-background",
} as const;

/** Full-width section band, the content inside is centred and capped. */
export default function Band({
  tone = "plain",
  children,
  testId,
}: {
  tone?: keyof typeof TONES;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <section className={`${TONES[tone]} px-4 sm:px-8 lg:px-14 xl:px-20 py-14 sm:py-20 lg:py-28`} data-testid={testId}>
      <div className="max-w-[1600px] mx-auto">{children}</div>
    </section>
  );
}
