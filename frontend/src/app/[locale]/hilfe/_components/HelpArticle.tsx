"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import HelpLightbox from "./HelpLightbox";
import type { ImageSize } from "../_lib/imageSizes";

/** Renders one help article. Sizes come from the server so pictures never get blown up. */
export default function HelpArticleView({
  markdown,
  sizes,
}: {
  markdown: string;
  sizes: Record<string, ImageSize>;
}) {
  const t = useTranslations("help");
  const [open, setOpen] = useState<{ src: string; alt: string } | null>(null);

  return (
    <>
    <article className="max-w-3xl min-w-0 text-base leading-relaxed" style={{ color: "var(--foreground)" }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="text-2xl font-bold mb-6">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-semibold mt-10 mb-3">{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-semibold mt-6 mb-2">{children}</h3>,
          p: ({ children }) => <p className="mb-4">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-5 mb-4 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 mb-4 space-y-1">{children}</ol>,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          a: ({ href, children }) => (
            <a href={String(href)} className="underline" style={{ color: "var(--kb-dark)" }}>
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code
              className="px-1.5 py-0.5 rounded text-sm"
              style={{ backgroundColor: "var(--surface-dim)" }}
            >
              {children}
            </code>
          ),
          blockquote: ({ children }) => (
            <blockquote
              className="pl-4 my-4"
              style={{ borderLeft: "3px solid var(--border)", color: "var(--foreground-soft)" }}
            >
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-4">
              <table className="w-full text-sm border-collapse">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="text-left px-2 py-1 font-semibold" style={{ borderBottom: "1px solid var(--border)" }}>
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-2 py-1" style={{ borderTop: "1px solid var(--border-soft)" }}>
              {children}
            </td>
          ),
          img: ({ src, alt }) => {
            const key = String(src);
            const size = sizes[key];
            const label = alt ?? "";
            return (
              <button
                type="button"
                onClick={() => setOpen({ src: key, alt: label })}
                aria-label={t("imageOpen", { alt: label })}
                className="block my-6 rounded-lg cursor-zoom-in"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={key}
                  alt={label}
                  width={size?.width}
                  height={size?.height}
                  className="max-w-full h-auto rounded-lg"
                  style={{ border: "1px solid var(--border)" }}
                />
              </button>
            );
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
      </article>
      {open && <HelpLightbox src={open.src} alt={open.alt} onClose={() => setOpen(null)} />}
    </>
  );
}
