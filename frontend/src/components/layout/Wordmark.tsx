/** The name of the platform as text, it replaces the logo wherever a link leads home. */
export const BRAND_NAME = "askFrancis";

const SIZES = { sm: "text-base", md: "text-lg" } as const;

export default function Wordmark({ size = "md", className = "" }: { size?: keyof typeof SIZES; className?: string }) {
  return (
    <span className={`${SIZES[size]} font-semibold tracking-tight leading-none whitespace-nowrap ${className}`.trim()}>
      {BRAND_NAME}
    </span>
  );
}
