"use client";

import { useEffect, useRef, useState, type ReactNode, type CSSProperties } from "react";
import { useTranslations } from "next-intl";

interface ExpandableTextProps {
  children: ReactNode;
  className?: string;
  clampClass?: string;
  style?: CSSProperties;
}

export default function ExpandableText({
  children,
  className = "",
  clampClass = "",
  style,
}: ExpandableTextProps) {
  const t = useTranslations("common");
  const [expanded, setExpanded] = useState(false);
  const [isClamped, setIsClamped] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) setIsClamped(el.scrollHeight > el.clientHeight + 1);
  }, [children]);

  return (
    <p
      ref={ref}
      className={`${className} ${expanded ? "" : clampClass} ${isClamped || expanded ? "cursor-pointer" : ""}`}
      style={style}
      onClick={
        isClamped || expanded
          ? (e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }
          : undefined
      }
      title={
        isClamped || expanded
          ? expanded
            ? t("collapseClick")
            : t("expandClick")
          : undefined
      }
    >
      {children}
    </p>
  );
}
