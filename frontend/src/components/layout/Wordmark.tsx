import Image from "next/image";

/** The name of the platform as text, for places that need it as a string. */
export const BRAND_NAME = "askFrancis";

const SIZES = { sm: { plate: "logo-plate logo-plate--sm", img: "h-5" }, md: { plate: "logo-plate", img: "h-6" } } as const;

/** The transparent logo on a white plate, the plate is styled in CSS so the ground stays adjustable. */
export default function Wordmark({ size = "md", className = "" }: { size?: keyof typeof SIZES; className?: string }) {
  const s = SIZES[size];
  return (
    <span className={`${s.plate} ${className}`.trim()}>
      <Image src="/logos/askfrancis-logo.svg" alt={BRAND_NAME} width={125} height={24} className={`${s.img} w-auto`} priority />
    </span>
  );
}
