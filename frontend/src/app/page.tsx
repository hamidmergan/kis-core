"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  SubtitlesIcon,
  TranslateIcon,
  SpeakerHighIcon,
  FilmSlateIcon,
  ImageSquareIcon,
  BookIcon,
  ArticleIcon,
  VideoIcon,
  PresentationChartIcon,
} from "@phosphor-icons/react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import { TOOL_CONFIG } from "@/lib/toolConfig";

const WORKFLOW_ICONS: Record<string, React.ElementType> = {
  screencast: PresentationChartIcon,
  "screencast-demo": FilmSlateIcon,
};

const TOOL_ICONS: Record<string, React.ElementType> = {
  translation: TranslateIcon,
  tts: SpeakerHighIcon,
  transcription: SubtitlesIcon,
  video_dubbing: VideoIcon,
  image: ImageSquareIcon,
  glossary: BookIcon,
  summary: ArticleIcon,
};

const ALL_WORKFLOWS = [
  {
    key: "screencast",
    title: "Screencast",
    description: "Aus PowerPoint-Dateien vertonte Videos mit übersetzten Folien generieren.",
    href: "/screencast",
  },
];

type Tool = { key: string; title: string; description: string; href: string; unavailable?: boolean };

const ALL_TOOLS: Tool[] = [
  { key: "translation",   title: "Translate",      description: "Dokumente in andere Sprachen übersetzen.", href: "/translation" },
  { key: "tts",           title: "Text-to-Speech", description: "Texte und Dokumente in Audio umwandeln.", href: "/tts" },
  { key: "transcription", title: "Speech-to-Text", description: "Audio- und Videoinhalte in Text oder Untertitel umwandeln.", href: "/transcription" },
  { key: "video_dubbing", title: "Video-Dubbing",  description: "Videos in andere Sprachen synchronisieren.", href: "/video-dubbing", unavailable: true },
  { key: "image",         title: "Image",          description: "Bilder erstellen, bearbeiten oder analysieren.", href: "/image" },
  { key: "summary",       title: "Summarize",      description: "Dokumente und Medieninhalte zusammenfassen.", href: "/summary" },
  { key: "glossary",      title: "Glossary",       description: "Begriffslisten für Übersetzungen und Skripte verwalten.", href: "/glossary" },
];

function ToolImage({ toolKey, title }: { toolKey: string; title: string }) {
  const cfg = TOOL_CONFIG[toolKey];
  if (cfg?.image) {
    const containPadding = toolKey === "tts" ? "p-4" : toolKey === "image" ? "p-2" : ["summary", "transcription", "translation", "glossary"].includes(toolKey) ? "p-1" : null;
    return (
      <div className="relative w-full h-36 overflow-hidden flex items-center justify-center">
        <Image
          src={cfg.image}
          alt={title}
          fill
          className={containPadding ? `object-contain ${containPadding}` : "object-cover"}
          sizes="(max-width: 768px) 100vw, (max-width: 1024px) 50vw, 33vw"
          loading="eager"
        />
      </div>
    );
  }
  // Fallback: colour gradient + icon
  const Icon = TOOL_ICONS[toolKey] ?? WORKFLOW_ICONS[toolKey] ?? ArticleIcon;
  const color = cfg?.color ?? "#668DA0";
  return (
    <div
      className="w-full h-36 flex items-center justify-center"
      style={{ background: `linear-gradient(135deg, ${color}22 0%, ${color}11 100%)` }}
    >
      <Icon size={48} weight="duotone" color={color} />
    </div>
  );
}

function WorkflowCard({ wf }: { wf: typeof ALL_WORKFLOWS[number] }) {
  const cfg = TOOL_CONFIG[wf.key];
  const color = cfg?.color ?? "#7C3AED";
  const Icon = WORKFLOW_ICONS[wf.key] ?? PresentationChartIcon;

  return (
    <Link
      href={wf.href}
      className="group flex rounded-xl overflow-hidden transition-all duration-200"
      style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-hover)")}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "var(--shadow)")}
    >
      {/* Image — left column, fixed width */}
      <div className="relative w-52 flex-shrink-0 overflow-hidden">
        {cfg?.image ? (
          <Image
            src={cfg.image}
            alt={wf.title}
            fill
            className="object-cover"
            sizes="208px"
            priority
          />
        ) : (
          <div
            className="w-full h-full flex items-center justify-center"
            style={{ background: `linear-gradient(135deg, ${color}22 0%, ${color}11 100%)` }}
          >
            <Icon size={48} weight="duotone" color={color} />
          </div>
        )}
      </div>

      {/* Text — right column */}
      <div className="flex flex-col justify-center p-6">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
          <h2 className="text-base font-semibold" style={{ color: "var(--text)" }}>{wf.title}</h2>
        </div>
        <p className="text-sm" style={{ color: "var(--muted)" }}>{wf.description}</p>
      </div>
    </Link>
  );
}

export default function HomePage() {
  const [disabledTools, setDisabledTools] = useState<Set<string> | null>(null);

  useEffect(() => {
    fetch("/api/admin/tools", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const disabled = new Set<string>(
          (d.tools ?? []).filter((t: { enabled: boolean }) => !t.enabled).map((t: { key: string }) => t.key)
        );
        setDisabledTools(disabled);
      })
      .catch(() => setDisabledTools(new Set()));
  }, []);

  if (disabledTools === null) return null;

  const workflows = ALL_WORKFLOWS.filter((w) => !disabledTools.has(w.key));
  const tools = ALL_TOOLS.filter((t) => !disabledTools.has(t.key));

  return (
    <ProtectedRoute>
      <Header showLogout />

      <div className="max-w-5xl mx-auto px-4 pt-10 pb-20 lg:pt-15 lg:pb-30">

        <h1 className="text-3xl font-bold mb-10" style={{ color: "var(--text)" }}>Willkommen bei KIS</h1>

        {/* ── Workflows ── */}
        {workflows.length > 0 && (
          <section className="mb-12">
            <p className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "var(--muted)" }}>
              Workflows
            </p>
            <div className="flex flex-col gap-4">
              {workflows.map((wf) => {
                const cfg = TOOL_CONFIG[wf.key];
                const color = cfg?.color ?? "#7C3AED";
                const Icon = WORKFLOW_ICONS[wf.key] ?? PresentationChartIcon;
                return (
                  <Link
                    key={wf.href}
                    href={wf.href}
                    className="group flex flex-col sm:flex-row sm:min-h-40 lg:min-h-45 rounded-xl overflow-hidden transition-all duration-200"
                    style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
                    onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-hover)")}
                    onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "var(--shadow)")}
                  >
                    {/* Bild — oben (mobile) / links (desktop) */}
                    <div className="relative h-40 sm:h-auto sm:w-64 sm:self-stretch flex-shrink-0 overflow-hidden">
                      {cfg?.image ? (
                        <Image
                          src={cfg.image}
                          alt={wf.title}
                          fill
                          className="object-contain p-0"
                          sizes="(max-width: 640px) 100vw, 256px"
                          priority
                        />
                      ) : (
                        <div
                          className="w-full h-full flex items-center justify-center"
                          style={{ background: `linear-gradient(135deg, ${color}22 0%, ${color}11 100%)` }}
                        >
                          <Icon size={48} weight="duotone" color={color} />
                        </div>
                      )}
                    </div>
                    {/* Text — unten (mobile) / rechts (desktop) */}
                    <div className="flex flex-col justify-center px-8 py-7">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                        <h2 className="text-lg font-semibold" style={{ color: "var(--text)" }}>{wf.title}</h2>
                      </div>
                      <p className="text-base" style={{ color: "var(--muted)" }}>{wf.description}</p>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        )}

        {/* ── Tools ── */}
        {tools.length > 0 && (
          <section>
            <p className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "var(--muted)" }}>
              Tools
            </p>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {tools.map((tool) => {
                const cfg = TOOL_CONFIG[tool.key];
                const color = cfg?.color ?? "#668DA0";

                if (tool.unavailable) {
                  return (
                    <div
                      key={tool.href}
                      className="rounded-xl overflow-hidden opacity-50 cursor-not-allowed"
                      style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
                    >
                      <ToolImage toolKey={tool.key} title={tool.title} />
                      <div className="p-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                          <h3 className="text-base font-semibold" style={{ color: "var(--muted)" }}>{tool.title}</h3>
                          <span
                            className="ml-auto text-xs px-2 py-0.5 rounded-full"
                            style={{ backgroundColor: "var(--border)", color: "var(--muted)" }}
                          >
                            Nicht verfügbar
                          </span>
                        </div>
                        <p className="text-base" style={{ color: "var(--muted)" }}>{tool.description}</p>
                      </div>
                    </div>
                  );
                }

                return (
                  <Link
                    key={tool.href}
                    href={tool.href}
                    className="group block rounded-xl overflow-hidden transition-all duration-200"
                    style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
                    onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-hover)")}
                    onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "var(--shadow)")}
                  >
                    <ToolImage toolKey={tool.key} title={tool.title} />
                    <div className="px-4 pt-0 pb-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                        <h3 className="text-base font-semibold" style={{ color: "var(--text)" }}>{tool.title}</h3>
                      </div>
                      <p className="text-base" style={{ color: "var(--muted)" }}>{tool.description}</p>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        )}

      </div>
    </ProtectedRoute>
  );
}
