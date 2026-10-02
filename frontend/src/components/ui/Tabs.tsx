"use client";

import { type ReactNode } from "react";

export interface TabItem<TKey extends string = string> {
  key: TKey;
  label: ReactNode;
  disabled?: boolean;
  badge?: ReactNode;
}

interface TabsProps<TKey extends string = string> {
  items: ReadonlyArray<TabItem<TKey>>;
  active: TKey;
  onChange: (key: TKey) => void;
  variant?: "underline" | "pill";
  className?: string;
}

export default function Tabs<TKey extends string = string>({
  items,
  active,
  onChange,
  variant = "underline",
  className = "",
}: TabsProps<TKey>) {
  if (variant === "pill") {
    return (
      // A border around the track, so the group stays visible even on a surface-coloured card,
      // and a hover on the inactive side, so it reads as a second thing to click, not plain text.
      <div className={`inline-flex gap-1 p-1 rounded-full border border-border bg-surface ${className}`} role="tablist">
        {items.map((item) => {
          const isActive = item.key === active;
          return (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              disabled={item.disabled}
              onClick={() => onChange(item.key)}
              className={`px-3.5 py-1.5 text-sm font-medium rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-2 ${
                isActive ? "bg-kb text-white" : "text-muted hover:bg-background hover:text-foreground"
              }`}
            >
              {item.label}
              {item.badge}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      className={`flex items-end gap-1 ${className}`}
      style={{ borderBottom: "1px solid var(--border)" }}
      role="tablist"
    >
      {items.map((item) => {
        const isActive = item.key === active;
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            disabled={item.disabled}
            onClick={() => onChange(item.key)}
            className={`px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-2 whitespace-nowrap rounded-t-md ${
              isActive ? "bg-kb/10 text-kb dark:text-foreground" : "text-muted hover:bg-surface hover:text-foreground"
            }`}
            style={{
              borderBottom: `2px solid ${isActive ? "var(--kb)" : "transparent"}`,
              marginBottom: "-1px",
            }}
          >
            {item.label}
            {item.badge}
          </button>
        );
      })}
    </div>
  );
}
