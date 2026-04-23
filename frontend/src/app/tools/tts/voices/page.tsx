"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import BackLink from "@/components/ui/BackLink";
import ElevenLabsTab from "./_tabs/ElevenLabsTab";
import KokoroTab from "./_tabs/KokoroTab";
import MylabTab from "./_tabs/MylabTab";
import type { VoicesTab } from "./_utils";


interface TabConfig {
  id: VoicesTab;
  label: string;
  enabled: boolean;
}


function StimmenPageInner() {
  const searchParams = useSearchParams();
  const [elevenlabsEnabled, setElevenlabsEnabled] = useState(true);
  const [kokoroEnabled, setKokoroEnabled] = useState(false);
  const [mylabEnabled, setMylabEnabled] = useState(false);
  const [activeTab, setActiveTab] = useState<VoicesTab>(
    (searchParams.get("tab") as VoicesTab | null) ?? "elevenlabs",
  );

  useEffect(() => {
    const tabFromUrl = searchParams.get("tab") as VoicesTab | null;
    fetch("/api/tts/providers", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const el = d.elevenlabs_enabled ?? true;
        const ko = d.kokoro_enabled ?? false;
        const ml = d.mylab_enabled ?? false;
        setElevenlabsEnabled(el);
        setKokoroEnabled(ko);
        setMylabEnabled(ml);
        if (tabFromUrl === "mylab" && ml) setActiveTab("mylab");
        else if (tabFromUrl === "kokoro" && ko) setActiveTab("kokoro");
        else if (tabFromUrl === "elevenlabs" && el) setActiveTab("elevenlabs");
        else if (!el) setActiveTab(ko ? "kokoro" : ml ? "mylab" : "elevenlabs");
      })
      .catch(() => {});
  }, []);

  const tabs: TabConfig[] = [
    { id: "elevenlabs", label: "ElevenLabs", enabled: elevenlabsEnabled },
    { id: "kokoro", label: "Kokoro TTS", enabled: kokoroEnabled },
    { id: "mylab", label: "THL myLab", enabled: mylabEnabled },
  ];

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <h1 className="text-xl font-bold mb-1">Verfügbare Stimmen</h1>

        <div className="flex gap-1 border-b border-gray-200 mb-6">
          {tabs.filter((t) => t.enabled).map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === id
                  ? "border-primary text-primary"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {activeTab === "elevenlabs" && <ElevenLabsTab enabled={elevenlabsEnabled} />}
        {activeTab === "kokoro" && <KokoroTab active={activeTab === "kokoro"} />}
        {activeTab === "mylab" && <MylabTab active={activeTab === "mylab"} />}
      </div>
    </ProtectedRoute>
  );
}


export default function StimmenPage() {
  return (
    <Suspense>
      <StimmenPageInner />
    </Suspense>
  );
}
