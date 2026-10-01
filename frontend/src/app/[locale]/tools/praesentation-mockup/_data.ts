// Vorlaeufige Route (siehe page.tsx) – diese Daten sind erfunden, nur fuers Aussehen.

export interface MockVorlage {
  id: string;
  name: string;
  accent: string;
}

export const VORLAGEN: MockVorlage[] = [
  { id: "t1", name: "Classic Blue", accent: "#004261" },
  { id: "t2", name: "Warm Sand", accent: "#B45309" },
  { id: "t3", name: "Fresh Green", accent: "#15803D" },
  { id: "t4", name: "Soft Violet", accent: "#534AB7" },
];

export interface MockSlide {
  id: string;
  role: string;
  title: string;
  bullets: string[];
  notes: string;
  imageMissing?: boolean;
}

// One slide short of what MOCK_SLIDE_COUNT promises, so the list ends on a skeleton row.
export const MOCK_SLIDES: MockSlide[] = [
  {
    id: "s1", role: "Deckblatt", title: "Digitalisierung im Mittelstand",
    bullets: ["Projektüberblick", "Zeitraum: Herbst 2026"],
    notes: "Begrüßung und kurze Vorstellung des Themas.",
  },
  {
    id: "s2", role: "Abschnitt", title: "Status quo",
    bullets: ["Papierbasierte Prozesse weit verbreitet", "Wenig Automatisierung im Mittelstand"],
    notes: "Hier auf die Umfrageergebnisse aus Kapitel 2 eingehen.",
  },
  {
    id: "s3", role: "Inhalt", title: "Drei zentrale Herausforderungen",
    bullets: ["Fachkräftemangel", "Fehlende Standards", "Hohe Investitionskosten"],
    notes: "Jede Herausforderung kurz mit einem Beispiel unterlegen.",
    imageMissing: true,
  },
];

export const MOCK_SLIDE_COUNT = MOCK_SLIDES.length + 1;
