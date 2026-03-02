"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";

const ALL_WORKFLOWS = [
  {
    key: "screencast",
    title: "Screencast",
    description:
      "Laden Sie eine deutsche PowerPoint-Präsentation hoch und erhalten Sie ein englischsprachiges Video mit übersetzten Folien und Sprachausgabe.",
    href: "/screencast",
  },
];

type Tool = { key: string; title: string; description: string; href: string; unavailable?: boolean };

const ALL_TOOLS: Tool[] = [
  {
    key: "translation",
    title: "Dokumentenübersetzung",
    description: "Übersetzen Sie Dokumente automatisch von Deutsch nach Englisch.",
    href: "/translation",
  },
  {
    key: "tts",
    title: "Text-to-Speech",
    description: "Lassen Sie Dokumente als MP3-Audiodatei vorlesen.",
    href: "/tts",
  },
  {
    key: "script",
    title: "Skript erstellen",
    description: "Erstellen Sie aus Dokumenten ein fließendes Vorleseskript.",
    href: "/script",
  },
  {
    key: "transcription",
    title: "Transkription",
    description: "Transkribieren oder übersetzen Sie Audio- und Videodateien zu Text, SRT oder VTT.",
    href: "/transcription",
  },
  {
    key: "video_dubbing",
    title: "Video-Dubbing",
    description: "Synchronisieren Sie ein Video automatisch in eine andere Sprache.",
    href: "/video-dubbing",
    unavailable: true,
  },
  {
    key: "image",
    title: "Bild-KI",
    description: "Bilder generieren, bearbeiten und analysieren mit KI.",
    href: "/image",
  },
  {
    key: "glossary",
    title: "Glossare",
    description: "Verwalten Sie Begriffslisten für konsistente Übersetzungen und Skripterstellung.",
    href: "/glossary",
  },
  {
    key: "summary",
    title: "Zusammenfassung",
    description: "Fassen Sie Dokumente, Audio- und Untertiteldateien automatisch zusammen.",
    href: "/summary",
  },
];

export default function HomePage() {
  const [disabledTools, setDisabledTools] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch("/api/admin/tools", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const disabled = new Set<string>(
          (d.tools ?? []).filter((t: { enabled: boolean }) => !t.enabled).map((t: { key: string }) => t.key)
        );
        setDisabledTools(disabled);
      })
      .catch(() => {});
  }, []);

  const workflows = ALL_WORKFLOWS.filter((w) => !disabledTools.has(w.key));
  const tools = ALL_TOOLS.filter((t) => !disabledTools.has(t.key));

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        {workflows.length > 0 && (
          <>
            <h1 className="text-xl font-bold text-gray-900 mb-1">Workflows</h1>
            <p className="text-sm text-gray-500 mb-4">
              Mehrstufige Abläufe, die mehrere Tools kombinieren.
            </p>
            <div className="grid gap-4 mb-10">
              {workflows.map((wf) => (
                <Link
                  key={wf.href}
                  href={wf.href}
                  className="block rounded-lg border border-[#b3d4f0] bg-[#e8f0fb] p-8 shadow-sm transition-shadow hover:shadow-md"
                >
                  <h2 className="text-lg font-semibold text-[#0066cc] mb-2">{wf.title}</h2>
                  <p className="text-sm text-gray-700">{wf.description}</p>
                </Link>
              ))}
            </div>
          </>
        )}

        {tools.length > 0 && (
          <>
            <h2 className="text-xl font-bold text-gray-900 mb-1">Tools</h2>
            <p className="text-sm text-gray-500 mb-4">
              Einzelne Tools für spezifische Aufgaben.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              {tools.map((tool) =>
                tool.unavailable ? (
                  <div
                    key={tool.href}
                    className="block rounded-lg border border-gray-200 bg-gray-50 p-6 shadow-sm opacity-60 cursor-not-allowed"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <h2 className="text-lg font-semibold text-gray-400">{tool.title}</h2>
                      <span className="text-xs font-medium text-gray-500 bg-gray-200 px-2 py-0.5 rounded-full">Nicht verfügbar</span>
                    </div>
                    <p className="text-sm text-gray-400">{tool.description}</p>
                  </div>
                ) : (
                  <Link
                    key={tool.href}
                    href={tool.href}
                    className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
                  >
                    <h2 className="text-lg font-semibold text-[#0066cc] mb-2">{tool.title}</h2>
                    <p className="text-sm text-gray-600">{tool.description}</p>
                  </Link>
                )
              )}
            </div>
          </>
        )}
      </div>
    </ProtectedRoute>
  );
}
