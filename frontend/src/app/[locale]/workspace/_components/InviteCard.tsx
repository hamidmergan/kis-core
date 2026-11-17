import type { ComponentType, HTMLAttributes, ReactNode } from "react";

const DEFAULT_LAYOUT = "rounded-xl p-4 flex-1 flex items-start gap-3";

interface InviteCardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title" | "style"> {
  icon: ComponentType<{ size?: number; weight?: "bold"; style?: React.CSSProperties }>;
  title: string;
  body: string;
  /** The buttons below the text. */
  children: ReactNode;
}

/** The card every invitation on the start page shares: icon, two lines and a row of buttons. */
export function InviteCard({ icon: Icon, title, body, children, className = DEFAULT_LAYOUT, ...rest }: InviteCardProps) {
  return (
    <div
      className={className}
      style={{ backgroundColor: "var(--surface-dim)", border: "1px solid var(--border-soft)" }}
      {...rest}
    >
      <Icon size={20} weight="bold" style={{ color: "var(--kb)", flexShrink: 0, marginTop: 2 }} />
      <div className="min-w-0 flex-1 self-stretch flex flex-col">
        <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{title}</p>
        <p className="text-sm mt-1" style={{ color: "var(--foreground-soft)" }}>{body}</p>
        <div className="flex items-stretch gap-2 mt-auto pt-3">{children}</div>
      </div>
    </div>
  );
}
