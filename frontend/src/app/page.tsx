"use client";

import Link from "next/link";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";

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
];

export default function HomePage() {
  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-xl font-bold text-gray-900 mb-1">Tools</h1>
        <p className="text-sm text-gray-500 mb-8">
          Wählen Sie ein Tool aus, um loszulegen.
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
