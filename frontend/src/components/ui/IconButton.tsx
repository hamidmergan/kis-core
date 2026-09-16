"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";

/** One consistent icon button for the whole app. */
const IconButton = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { size?: "sm" | "md" | "lg" }
>(({ size = "md", className = "", style, children, ...props }, ref) => {
  const sizeClass = size === "sm" ? "w-6 h-6" : size === "lg" ? "w-10 h-10" : "w-7 h-7";
  return (
    <button
      ref={ref}
      type="button"
      className={`${sizeClass} flex items-center justify-center rounded-full btn-icon flex-shrink-0 ${className}`}
      style={{ backgroundColor: "var(--surface-dim)", ...style }}
      {...props}
    >
      {children}
    </button>
  );
});

IconButton.displayName = "IconButton";
export default IconButton;
