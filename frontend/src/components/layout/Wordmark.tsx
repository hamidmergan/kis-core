import Image from "next/image";

/** The name of the platform as text, it replaces the logo wherever a link leads home. */
export const BRAND_NAME = "askFrancis";

const SIZES = { sm: { text: "text-base", icon: "h-5" }, md: { text: "text-lg", icon: "h-6" } } as const;

export default function Wordmark({ size = "md", className = "" }: { size?: keyof typeof SIZES; className?: string }) {
  const s = SIZES[size];
  return (
    <span className={`inline-flex items-center gap-1.5 ${s.text} font-semibold tracking-tight leading-none whitespace-nowrap ${className}`.trim()}>
      {/* The green bird of the KIS logo stays as the icon left of the name. */}
      <Image src="/logos/kis-vogel.svg" alt="" width={154} height={78} className={`${s.icon} w-auto`} priority />
      {BRAND_NAME}
    </span>
  );
}
