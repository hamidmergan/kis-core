interface SpinnerProps {
  size?: "xs" | "sm" | "md" | "lg";
  color?: "primary" | "current";
  label?: string;
  className?: string;
}

const sizes = {
  xs: "w-3 h-3 border-[1.5px]",
  sm: "w-3.5 h-3.5 border-[1.5px]",
  md: "w-5 h-5 border-2",
  lg: "w-8 h-8 border-2",
};

const colors = {
  primary: "border-kb border-t-transparent",
  current: "border-current border-t-transparent",
};

export default function Spinner({ size = "md", color = "primary", label, className = "" }: SpinnerProps) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`} role="status" aria-live="polite">
      <span className={`${sizes[size]} ${colors[color]} rounded-full animate-spin inline-block shrink-0`} />
      {label && <span className="text-sm text-muted">{label}</span>}
    </span>
  );
}
