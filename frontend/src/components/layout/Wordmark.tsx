import Image from "next/image";

/** The name of the platform as text, for places that need it as a string. */
export const BRAND_NAME = "ASK Francis";

// The wordmark has no bird, so it is flatter: these heights keep the width the old logo had.
const SIZES = { sm: { plate: "logo-plate logo-plate--sm", img: "h-3.5" }, md: { plate: "logo-plate", img: "h-[1.0625rem]" } } as const;

/** The transparent logo on a white plate, the plate is styled in CSS so the ground stays adjustable. */
export default function Wordmark({ size = "md", className = "", birdOnly = false }: { size?: keyof typeof SIZES; className?: string; birdOnly?: boolean }) {
  const s = SIZES[size];
  if (birdOnly) {
    return (
      <span className={`${s.plate} ${className}`.trim()}>
        <Image src="/logos/kis-vogel.svg" alt={BRAND_NAME} width={154} height={78} className={`${s.img} w-auto`} priority />
      </span>
    );
  }
  return (
    <span className={`${s.plate} ${className}`.trim()}>
      <Image src="/logos/ask-francis-logo-transparent-black.svg" alt={BRAND_NAME} width={98} height={13} className={`${s.img} w-auto`} priority />
    </span>
  );
}
