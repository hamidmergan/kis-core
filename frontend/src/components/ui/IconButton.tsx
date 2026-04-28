"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";

/**
 * Consistent icon button used across the app.
 * rounded-full, hover:outline-primary, centered flex, theme-aware color.
 */
const IconButton = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { size?: "sm" | "md" }
>(({ size = "md", className = "", style, children, ...props }, ref) => {
  const sizeClass = size === "sm" ? "w-6 h-6" : "w-7 h-7";
  return (
    <button
      ref={ref}
      type="button"
      className={`${sizeClass} flex items-center justify-center rounded-full text-[var(--muted)] hover:text-primary hover:outline-2 hover:outline-primary transition flex-shrink-0 ${className}`}
      style={{ backgroundColor: "var(--surface-dim)", ...style }}
      {...props}
    >
      {children}
    </button>
  );
});

IconButton.displayName = "IconButton";
export default IconButton;
