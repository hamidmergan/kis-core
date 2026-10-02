import type { ReactNode } from "react";

const TONES = {
  plain: "bg-background",
  tint: "bg-surface",
  hero: "bg-gradient-to-b from-kb/10 via-kb/5 to-background",
  accent: "bg-kb text-on-accent",
} as const;

/** Full-width section band, the content inside is centred and capped. */
export default function Band({
  tone = "plain",
  children,
  testId,
  fill = false,
}: {
  tone?: keyof typeof TONES;
  children: ReactNode;
  testId?: string;
  fill?: boolean;
}) {
  // A filling band takes the screen below the header, --band-top is measured by useBandTop.
  const height = fill
    ? "flex flex-col justify-center min-h-[calc(100dvh-var(--band-top,0px))] py-10 sm:py-14"
    : "py-14 sm:py-20 lg:py-24";
  return (
    <section className={`${TONES[tone]} ${height} px-4 sm:px-8 lg:px-14 xl:px-20`} data-testid={testId}>
      <div className="w-full max-w-[1600px] mx-auto">{children}</div>
    </section>
  );
}
