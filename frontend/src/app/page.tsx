"use client";

import Link from "next/link";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";

const workflows = [
  {
    title: "Screencast",
    description:
      "Laden Sie eine deutsche PowerPoint-Präsentation hoch und erhalten Sie ein englischsprachiges Video mit übersetzten Folien und Sprachausgabe.",
    href: "/screencast",
  },
];

const tools = [
  {
    title: "Dokumentenübersetzung",
    description: "Übersetzen Sie Dokumente automatisch von Deutsch nach Englisch.",
    href: "/uebersetzung",
  },
  {
    title: "Text-to-Speech",
    description: "Lassen Sie Dokumente als MP3-Audiodatei vorlesen.",
    href: "/tts",
  },
  {
    title: "Skript erstellen",
    description: "Erstellen Sie aus Dokumenten ein fließendes Vorleseskript.",
    href: "/skript",
  },
  {
    title: "Transkription",
    description: "Transkribieren oder übersetzen Sie Audio- und Videodateien zu Text, SRT oder VTT.",
    href: "/transcription",
  },
  {
    title: "Video-Dubbing",
    description: "Synchronisieren Sie ein Video automatisch in eine andere Sprache.",
    href: "/video-dubbing",
  },
];

export default function HomePage() {
  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Workflows section */}
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

        {/* Tools section */}
        <h2 className="text-xl font-bold text-gray-900 mb-1">Tools</h2>
        <p className="text-sm text-gray-500 mb-4">
          Einzelne Tools für spezifische Aufgaben.
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
          {tools.map((tool) => (
            <Link
              key={tool.href}
              href={tool.href}
              className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
            >
              <h2 className="text-lg font-semibold text-[#0066cc] mb-2">{tool.title}</h2>
              <p className="text-sm text-gray-600">{tool.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </ProtectedRoute>
  );
}
