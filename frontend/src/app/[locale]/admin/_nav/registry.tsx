"use client";

/**
 * Der Navigationsbaum des Adminbereichs, an einer Stelle.
 *
 * Vorher stand er dreifach in page.tsx: als Tab-Union, als NAV-Array und als
 * Kette aus {tab === "x" && <XTab/>}. Eine neue Seite hiess: drei Stellen
 * anfassen und hoffen, keine vergessen zu haben.
 *
 * Seitenleiste, Adresse, Seitentitel und Kruemelpfad lesen jetzt alle hier.
 * Eine neue Seite ist ein Eintrag.
 *
 * Das Feld `world` sagt, welches der beiden Produkte eine Seite betrifft. KIS
 * hat zwei: die globalen Tools auf der Startseite und den KI-Assistenten im
 * Modul. Wer das nicht auseinanderhaelt, landet wieder bei Namen wie "Tools
 * Kontext-Budget", das trotz seines Namens den Assistenten steuert.
 */

import type { ComponentType } from "react";
import {
  Bird,
  GearSix,
  Notebook,
  Palette,
  Sparkle,
  Toolbox,
  Users,
  type Icon,
} from "@phosphor-icons/react";

/** Welches Produkt eine Seite betrifft. */
export type World = "tools" | "aia" | "both" | "dev";

/**
 * Rang eines Bereichs in der Seitenleiste. Zwischen zwei Raengen zieht die
 * Leiste eine Linie.
 *
 * Ohne diese Trennung sehen sechs Punkte gleichrangig aus, obwohl sie es nicht
 * sind: zwei davon sind die Produkte, die anderen sind Verwaltung drumherum.
 * Genau die Zweiteilung, um die sich der ganze Umbau dreht, soll beim Oeffnen
 * ins Auge springen.
 */
export type Rank = "product" | "admin" | "dev";

/** Reihenfolge der Raenge in der Leiste. */
export const RANKS: Rank[] = ["product", "admin", "dev"];

/** Reiter innerhalb einer Seite. Nur wo ein Gegenstand in zwei Sichten
 *  zerfaellt: Sprachniveau (Einstufung und KI-Verhalten) und Anbieter (die
 *  Anbieter selbst und die Zuordnung zu den Funktionen). Reiter stehen auf der
 *  Seite, nicht in der Seitenleiste. */
export interface AdminTab {
  slug: string;
  /** Schluessel unter admin.sections.<bereich>.<seite>.tabs */
  labelKey: string;
  Component: ComponentType;
}

/** Zweite Ebene: eine Unterseite, klappt in der Seitenleiste auf. */
export interface AdminPage {
  slug: string;
  /** Schluessel unter admin.sections.<bereich> */
  key: string;
  world: World;
  Component?: ComponentType;
  tabs?: AdminTab[];
  /** Startseite von /admin. Genau eine Seite traegt das. Ohne Markierung
   *  faellt die Wahl auf die erste Seite des ersten Bereichs. */
  home?: true;
  /** Nicht in der Seitenleiste zeigen, Adresse bleibt aber gueltig. Fuer
   *  Seiten, die man nur ueber einen Absprung aus einer anderen Seite
   *  erreicht und die als eigener Punkt einen falschen Eindruck machen. */
  hidden?: true;
}

/** Erste Ebene. Ohne `pages` ist der Bereich selbst die Seite, entweder mit
 *  einem `Component` oder mit eigenen `tabs`. */
export interface AdminSection {
  slug: string;
  /** Schluessel unter admin.sections */
  key: string;
  Icon: Icon;
  world: World;
  rank: Rank;
  pages?: AdminPage[];
  Component?: ComponentType;
  /** Schluessel unter admin.sections.<bereich>.tabs */
  tabs?: AdminTab[];
}

import ToolReleasePage from "../_pages/werkzeuge/release";
import ToolJobsPage from "../_pages/werkzeuge/jobs";
import ToolStatsPage from "../_pages/werkzeuge/stats";

import SourcesPage from "../_pages/assistent/sources";
import AnswersPage from "../_pages/assistent/answers";
import LanguageLevelPage from "../_pages/assistent/language-level";
import AiBehaviourPage from "../_pages/assistent/behaviour";
import AiaUsagePage from "../_pages/assistent/usage";

import ProviderListPage from "../_pages/anbieter/list";
import ProviderRoutesPage from "../_pages/anbieter/routes";

import PendingPage from "../_pages/nutzer/pending";
import WhitelistPage from "../_pages/nutzer/whitelist";
import UsersPage from "../_pages/nutzer/users";
import RolesPage from "../_pages/nutzer/roles";
import QuotaPage from "../_pages/nutzer/quota";

import AppearancePage from "../_pages/appearance";
import SystemPage from "../_pages/system";
import HildePage from "../_pages/mascot/hilde";
import FrancisPage from "../_pages/mascot/francis";

export const SECTIONS: AdminSection[] = [
  // Reihenfolge: die beiden Produkte oben, alles andere ist Zuarbeit.
  // Wer die Leiste zum ersten Mal sieht, soll sofort erkennen, dass KIS aus
  // zwei getrennten Welten besteht. Nutzer, Anbieter, Oberflaeche und System
  // sind Verwaltung drumherum, Maskottchen ist Entwicklerkram und steht
  // abgetrennt ganz unten.
  {
    slug: "werkzeuge",
    key: "werkzeuge",
    Icon: Toolbox,
    world: "tools",
    rank: "product",
    pages: [
      { slug: "freigabe", key: "release", world: "tools", Component: ToolReleasePage },
      { slug: "auftraege", key: "jobs", world: "tools", Component: ToolJobsPage, home: true },
      { slug: "statistik", key: "stats", world: "tools", Component: ToolStatsPage },
    ],
  },
  {
    slug: "ki-assistent",
    key: "assistent",
    Icon: Notebook,
    world: "aia",
    rank: "product",
    pages: [
      { slug: "quellen", key: "sources", world: "aia", Component: SourcesPage },
      { slug: "antworten", key: "answers", world: "aia", Component: AnswersPage },
      // Eine Seite, zwei Reiter. Einstufung und KI-Verhalten gehoeren zum
      // selben Gegenstand: der eine Reiter schaltet den Test ein und legt fest
      // was er abfragt, der andere sagt wie die KI dabei fragt und urteilt.
      // Als zwei Punkte in der Leiste sahen sie aus wie zwei Themen.
      {
        slug: "sprachniveau",
        key: "level",
        world: "aia",
        tabs: [
          { slug: "einstufung", labelKey: "assessment", Component: LanguageLevelPage },
          { slug: "ki-verhalten", labelKey: "behaviour", Component: AiBehaviourPage },
        ],
      },
      { slug: "nutzung", key: "usage", world: "aia", Component: AiaUsagePage },
    ],
  },
  // Ein Punkt in der Leiste, zwei Reiter auf der Seite. Anbieter und
  // Funktionen sind zwei Sichten auf dieselbe Sache: erst traegt man einen
  // Anbieter ein, dann sagt man welche Funktion ihn nutzt. Als zwei
  // Unterpunkte sahen sie aus wie zwei Themen.
  {
    slug: "anbieter",
    key: "anbieter",
    Icon: Sparkle,
    world: "both",
    rank: "admin",
    tabs: [
      { slug: "liste", labelKey: "list", Component: ProviderListPage },
      { slug: "funktionen", labelKey: "routes", Component: ProviderRoutesPage },
    ],
  },
  {
    slug: "nutzer",
    key: "nutzer",
    Icon: Users,
    world: "both",
    rank: "admin",
    pages: [
      { slug: "ausstehend", key: "pending", world: "both", Component: PendingPage },
      { slug: "whitelist", key: "whitelist", world: "both", Component: WhitelistPage },
      { slug: "alle-nutzer", key: "users", world: "both", Component: UsersPage },
      { slug: "rollen", key: "roles", world: "both", Component: RolesPage },
      // Kein eigener Punkt in der Leiste: die Seite ist ein Absprung aus
      // "Alle Nutzer", erst Nutzer waehlen, dann dessen Kontingente samt
      // Standardwerten sehen. Als Punkt sah sie aus wie eine Seite, die man
      // ohne Nutzer aufrufen kann, und war dann leer.
      { slug: "kontingente", key: "quota", world: "both", Component: QuotaPage, hidden: true },
    ],
  },
  {
    slug: "oberflaeche",
    key: "appearance",
    Icon: Palette,
    world: "both",
    rank: "admin",
    Component: AppearancePage,
  },
  {
    slug: "system",
    key: "system",
    Icon: GearSix,
    world: "both",
    rank: "admin",
    Component: SystemPage,
  },
  {
    slug: "maskottchen",
    key: "mascot",
    Icon: Bird,
    world: "dev",
    rank: "dev",
    pages: [
      { slug: "hilde", key: "hilde", world: "dev", Component: HildePage },
      { slug: "francis", key: "francis", world: "dev", Component: FrancisPage },
    ],
  },
];

export interface Resolved {
  section: AdminSection;
  page?: AdminPage;
  /** Adresse ohne /admin-Präfix, immer vollständig. Für Weiterleitungen. */
  path: string;
}

/**
 * Pfadsegmente auf einen Eintrag abbilden. Unvollständige Pfade werden nach
 * unten aufgefüllt (/admin -> erster Bereich -> erste Seite), unbekannte
 * geben null, damit der Aufrufer weiterleiten kann statt leer zu rendern.
 */
export function resolve(segments: string[]): Resolved | null {
  if (!segments[0]) {
    const start = home();
    if (start) return start;
  }
  const section = segments[0]
    ? SECTIONS.find((s) => s.slug === segments[0])
    : SECTIONS[0];
  if (!section) return null;

  if (!section.pages) {
    return { section, path: section.slug };
  }

  const page = segments[1]
    ? section.pages.find((p) => p.slug === segments[1])
    : section.pages[0];
  if (!page) return null;

  return { section, page, path: `${section.slug}/${page.slug}` };
}

/**
 * Die markierte Startseite. /admin landet dort statt auf der ersten Seite des
 * ersten Bereichs: wer den Adminbereich oeffnet, will meist wissen ob alles
 * laeuft, und das steht bei den Auftraegen samt Auslastung.
 */
export function home(): Resolved | null {
  for (const section of SECTIONS) {
    const page = section.pages?.find((p) => p.home);
    if (page) return { section, page, path: `${section.slug}/${page.slug}` };
  }
  return null;
}

/** Alle Adressen, fuer Tests und zum Nachschlagen. */
export function allPaths(): string[] {
  return SECTIONS.flatMap((s) =>
    s.pages ? s.pages.map((p) => `${s.slug}/${p.slug}`) : [s.slug],
  );
}
