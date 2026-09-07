"use client";

import { useLinkStatus } from "next/link";
import Spinner from "./Spinner";

interface LinkBusyProps {
  size?: "xs" | "sm" | "md";
  color?: "primary" | "current";
  className?: string;
  /** Shown while the link is idle, so an icon can give way to the spinner. */
  children?: React.ReactNode;
}

/** Sits inside a Link and shows the spinner while that link is loading. */
export default function LinkBusy({ size = "sm", color = "current", className = "", children }: LinkBusyProps) {
  const { pending } = useLinkStatus();
  if (pending) return <Spinner size={size} color={color} className={className} />;
  return <>{children ?? null}</>;
}
