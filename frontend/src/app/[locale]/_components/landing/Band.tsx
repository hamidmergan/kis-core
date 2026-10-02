import type { ReactNode } from "react";

const TONES = {
  plain: "bg-background",
  tint: "bg-surface",
  hero: "bg-kb/10",
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
  // A filling band takes the screen below the header from tablet width on, on a phone it stays as tall as its content, --band-top comes from useBandTop and --zoom from the page.
  const height = fill
    ? "py-6 @min-[40rem]:flex @min-[40rem]:flex-col @min-[40rem]:justify-center @min-[40rem]:min-h-[calc((100dvh-var(--band-top,0px))/var(--zoom,1))] @min-[40rem]:py-10"
    : "py-14 @min-[40rem]:py-20 @min-[64rem]:py-24";
  return (
    <section className={`${TONES[tone]} ${height} px-4 @min-[40rem]:px-8 @min-[64rem]:px-14 @min-[80rem]:px-20`} data-testid={testId}>
      <div className="w-full max-w-[1600px] mx-auto">{children}</div>
    </section>
  );
}
