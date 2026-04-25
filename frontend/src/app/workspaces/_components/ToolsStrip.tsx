"use client";

import Image from "next/image";
import Link from "next/link";
import { useRef } from "react";
import { useEnabledTools } from "@/hooks/useEnabledTools";
import { useDragScroll } from "@/hooks/useDragScroll";
import { TOOL_CONFIG } from "@/lib/toolConfig";

type StripTool = { key: string; title: string; href: string };

const STRIP_TOOLS: StripTool[] = [
  { key: "translation",   title: "Übersetzung",     href: "/tools/translate"  },
  { key: "tts",           title: "Text in Sprache", href: "/tools/tts"        },
  { key: "transcription", title: "Sprache in Text", href: "/tools/stt"        },
  { key: "image",         title: "Bildgenerierung", href: "/tools/image"      },
  { key: "summary",       title: "Zusammenfassung", href: "/tools/summarize"  },
  { key: "glossary",      title: "Glossar",         href: "/tools/glossary"   },
  { key: "screencast",    title: "Screencast",      href: "/tools/screencast" },
];

const LARGER_IMAGE_KEYS = new Set(["translation", "transcription", "summary"]);

export default function ToolsStrip() {
  const { loaded, isToolEnabled } = useEnabledTools();
  const scrollerRef = useRef<HTMLDivElement>(null);
  useDragScroll(scrollerRef);

  if (!loaded) return null;

  const tools = STRIP_TOOLS.filter((t) => isToolEnabled(t.key));
  if (tools.length === 0) return null;

  return (
    <section className="mb-20">
      <h2 className="text-xl font-semibold mb-4">Tools</h2>

      <div
        ref={scrollerRef}
        className="flex sm:grid sm:grid-cols-7 gap-3 overflow-x-auto sm:overflow-visible scrollbar-hide touch-pan-x cursor-grab active:cursor-grabbing -mx-4 px-4 sm:mx-0 sm:px-0"
      >
        {tools.map((tool) => {
          const cfg = TOOL_CONFIG[tool.key];
          const image = cfg?.image;
          return (
            <Link
              key={tool.key}
              href={tool.href}
              className="group flex-shrink-0 w-[38vw] sm:w-auto aspect-square rounded-xl overflow-hidden transition-all flex flex-col no-underline select-none"
              style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
              onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-hover)")}
              onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "var(--shadow)")}
              draggable={false}
            >
              <div className="relative flex-1 w-full">
                {image && (
                  <Image
                    src={image}
                    alt=""
                    fill
                    sizes="(max-width: 640px) 112px, 140px"
                    className={`object-contain p-0.5 ${LARGER_IMAGE_KEYS.has(tool.key) ? "scale-125" : ""}`}
                    draggable={false}
                    unoptimized
                  />
                )}
              </div>
              <div className="px-2 pb-2 pt-0 text-center">
                <span
                  className="text-[11.5px] font-semibold truncate block"
                  style={{ color: "var(--foreground)" }}
                >
                  {tool.title}
                </span>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
