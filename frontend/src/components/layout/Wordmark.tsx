import Image from "next/image";

/** The name of the platform as text, for places that need it as a string. */
export const BRAND_NAME = "askFrancis";

const SIZES = { sm: "h-7", md: "h-8" } as const;

/** The logo on its white plate, the name as outlines next to the bird, it leads home wherever a link wraps it. */
export default function Wordmark({ size = "md", className = "" }: { size?: keyof typeof SIZES; className?: string }) {
  return (
    <Image
      src="/logos/askfrancis-logo-plate.svg"
      alt={BRAND_NAME}
      width={143}
      height={34}
      className={`${SIZES[size]} w-auto ${className}`.trim()}
      priority
    />
  );
}
