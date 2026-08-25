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
import { PERM } from "@/lib/permissions";
import {
  Bird,
  ChartBar,
  GearSix,
  Notebook,
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
  /** Rechte-Schluessel, ohne den der Reiter nicht erscheint.
   *
   *  Nur wo die Reiter wirklich getrennte Gegenstaende sind, also bei der
   *  Statistik. Sprachniveau und Anbieter lassen das leer: dort liegen die
   *  Werte im selben Datensatz, ein getrenntes Recht koennte der Torwaechter
   *  nicht halten. */
  perm?: string;
}

/** Zweite Ebene: eine Unterseite, klappt in der Seitenleiste auf. */
export interface AdminPage {
  slug: string;
  /** Schluessel unter admin.sections.<bereich> */
  key: string;
  world: World;
  /** Rechte-Schluessel, ohne den die Seite weder in der Leiste steht noch
   *  ueber ihre Adresse erreichbar ist. Siehe lib/permissions. */
  perm: string;
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
  /** Nur fuer Bereiche ohne Unterseiten. Bereiche mit Unterseiten sind
   *  sichtbar, sobald eine ihrer Seiten sichtbar ist. */
  perm?: string;
  pages?: AdminPage[];
  Component?: ComponentType;
  /** Schluessel unter admin.sections.<bereich>.tabs */
  tabs?: AdminTab[];
}

import ToolReleasePage from "../_pages/werkzeuge/release";
import ToolJobsPage from "../_pages/werkzeuge/jobs";
import ToolLimitsPage from "../_pages/werkzeuge/limits";

import SourcesPage from "../_pages/assistent/sources";
import LanguageLevelPage from "../_pages/assistent/language-level";
import AiBehaviourPage from "../_pages/assistent/behaviour";

import StatistikNutzerPage from "../_pages/statistik/nutzer";
import StatistikWerkzeugePage from "../_pages/statistik/werkzeuge";
import StatistikAssistentPage from "../_pages/statistik/assistent";
import StatistikModellePage from "../_pages/statistik/modelle";

import ProviderListPage from "../_pages/anbieter/list";
import ProviderRoutesPage from "../_pages/anbieter/routes";

import PendingPage from "../_pages/nutzer/pending";
import WhitelistPage from "../_pages/nutzer/whitelist";
import UsersPage from "../_pages/nutzer/users";
import RolesPage from "../_pages/nutzer/roles";
import QuotaPage from "../_pages/nutzer/quota";

import SystemPage from "../_pages/system";
import HildePage from "../_pages/mascot/hilde";
import FrancisPage from "../_pages/mascot/francis";

export const SECTIONS: AdminSection[] = [
  // Reihenfolge: die beiden Produkte oben, alles andere ist Zuarbeit.
  // Wer die Leiste zum ersten Mal sieht, soll sofort erkennen, dass KIS aus
  // zwei getrennten Welten besteht. Nutzer, Anbieter und System sind
  // Verwaltung drumherum, Maskottchen ist Entwicklerkram und steht
  // abgetrennt ganz unten.
  {
    slug: "werkzeuge",
    key: "werkzeuge",
    Icon: Toolbox,
    world: "tools",
    rank: "product",
    pages: [
      { slug: "freigabe", key: "release", world: "tools", perm: PERM.toolsRelease, Component: ToolReleasePage },
      { slug: "auftraege", key: "jobs", world: "tools", perm: PERM.toolsJobs, Component: ToolJobsPage, home: true },
      { slug: "grenzen", key: "limits", world: "tools", perm: PERM.toolsLimits, Component: ToolLimitsPage },
    ],
  },
  {
    slug: "ki-assistent",
    key: "assistent",
    Icon: Notebook,
    world: "aia",
    rank: "product",
    pages: [
      // Quellen traegt auch die beiden Kontext-Budgets. Sie hatten einen
      // eigenen Reiter "Antworten", der aber nichts ueber Antworten sagte:
      // beide Zahlen zaehlen Quelltext.
      { slug: "quellen", key: "sources", world: "aia", perm: PERM.aiaSources, Component: SourcesPage },
      // Eine Seite, zwei Reiter. Einstufung und KI-Verhalten gehoeren zum
      // selben Gegenstand: der eine Reiter schaltet den Test ein und legt fest
      // was er abfragt, der andere sagt wie die KI dabei fragt und urteilt.
      // Als zwei Punkte in der Leiste sahen sie aus wie zwei Themen.
      {
        slug: "sprachniveau",
        key: "level",
        world: "aia",
        // Beide Reiter haengen an einem Recht. Ihre Werte liegen im selben
        // Datensatz, eine Trennung koennte der Torwaechter nicht halten.
        perm: PERM.aiaLevel,
        tabs: [
          { slug: "einstufung", labelKey: "assessment", Component: LanguageLevelPage },
          { slug: "ki-verhalten", labelKey: "behaviour", Component: AiBehaviourPage },
        ],
      },
    ],
  },
  // Zahlen zum Lesen, nicht Knoepfe zum Drehen. Die eigentliche Trennlinie im
  // Adminbereich laeuft nicht zwischen den beiden Produkten, sondern zwischen
  // Einstellen und Nachschauen. Deshalb stehen die Zahlen beider Produkte hier
  // zusammen und nicht verstreut in ihren Bereichen.
  //
  // Jeder Reiter traegt sein eigenes Recht. Die zwei umgezogenen behalten das
  // alte, sonst haetten bestehende Rollen ueber Nacht den Zugang verloren.
  {
    slug: "statistik",
    key: "statistik",
    Icon: ChartBar,
    world: "both",
    rank: "admin",
    // Nutzer zuerst: wer den Bereich oeffnet, will meist wissen, ob gerade
    // jemand da ist, nicht wie viele Screencasts letzten Monat liefen.
    tabs: [
      { slug: "nutzer", labelKey: "nutzer", perm: PERM.statsUsers, Component: StatistikNutzerPage },
      { slug: "werkzeuge", labelKey: "werkzeuge", perm: PERM.toolsStats, Component: StatistikWerkzeugePage },
      { slug: "ki-assistent", labelKey: "assistent", perm: PERM.aiaUsage, Component: StatistikAssistentPage },
      { slug: "modelle", labelKey: "modelle", perm: PERM.statsModels, Component: StatistikModellePage },
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
    perm: PERM.providers,
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
      { slug: "ausstehend", key: "pending", world: "both", perm: PERM.usersPending, Component: PendingPage },
      { slug: "whitelist", key: "whitelist", world: "both", perm: PERM.usersWhitelist, Component: WhitelistPage },
      { slug: "alle-nutzer", key: "users", world: "both", perm: PERM.usersAll, Component: UsersPage },
      { slug: "rollen", key: "roles", world: "both", perm: PERM.usersRoles, Component: RolesPage },
      // Kein eigener Punkt in der Leiste: die Seite ist ein Absprung aus
      // "Alle Nutzer", erst Nutzer waehlen, dann dessen Kontingente samt
      // Standardwerten sehen. Als Punkt sah sie aus wie eine Seite, die man
      // ohne Nutzer aufrufen kann, und war dann leer.
      { slug: "kontingente", key: "quota", world: "both", perm: PERM.usersAll, Component: QuotaPage, hidden: true },
    ],
  },
  // System traegt auch die beiden Karten, die vorher unter "Oberflaeche"
  // standen: Beschriftung der Workspaces und der Hinweis auf der Startseite.
  // Ein eigener Punkt in der Leiste fuer zwei Karten, die genau wie der
  // Wartungsmodus fuer die ganze Plattform gelten, war eine Trennung zu viel.
  {
    slug: "system",
    key: "system",
    Icon: GearSix,
    world: "both",
    rank: "admin",
    perm: PERM.system,
    Component: SystemPage,
  },
  {
    slug: "maskottchen",
    key: "mascot",
    Icon: Bird,
    world: "dev",
    rank: "dev",
    pages: [
      { slug: "hilde", key: "hilde", world: "dev", perm: PERM.mascot, Component: HildePage },
      { slug: "francis", key: "francis", world: "dev", perm: PERM.mascot, Component: FrancisPage },
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
 * laeuft, und das steht bei den Auftraegen.
 */
export function home(): Resolved | null {
  for (const section of SECTIONS) {
    const page = section.pages?.find((p) => p.home);
    if (page) return { section, page, path: `${section.slug}/${page.slug}` };
  }
  return null;
}

/**
 * Wer was sehen darf.
 *
 * Der Bereich gehoert nicht mehr einer Rolle, sondern zerfaellt in Seiten, die
 * einzeln vergeben werden. Deshalb muss die Leiste filtern und nicht nur die
 * Tuer bewachen: eine Rolle, die nur das Sprachniveau pflegt, soll auch nur
 * diesen einen Punkt sehen.
 *
 * Der Server prueft jede Anfrage selbst. Hier geht es darum, niemandem eine
 * Tuer zu zeigen, die hinter einem 403 liegt.
 */
export function pageAllowed(page: AdminPage, keys: string[]): boolean {
  return keys.includes(page.perm);
}

/** Reiter ohne eigenes Recht haengen am Recht ihres Bereichs. */
export function tabAllowed(tab: AdminTab, section: AdminSection, keys: string[]): boolean {
  if (tab.perm) return keys.includes(tab.perm);
  return !!section.perm && keys.includes(section.perm);
}

/** Die sichtbaren Reiter eines Bereichs oder einer Seite. */
export function allowedTabs(
  tabs: AdminTab[] | undefined,
  section: AdminSection,
  keys: string[],
): AdminTab[] {
  return (tabs ?? []).filter((t) => tabAllowed(t, section, keys));
}

export function sectionAllowed(section: AdminSection, keys: string[]): boolean {
  if (section.pages) return section.pages.some((p) => pageAllowed(p, keys));
  if (section.tabs?.some((t) => t.perm)) return allowedTabs(section.tabs, section, keys).length > 0;
  return !!section.perm && keys.includes(section.perm);
}

/** Die Bereiche samt ihrer erlaubten Seiten und Reiter. Leere fallen weg. */
export function allowedSections(keys: string[]): AdminSection[] {
  return SECTIONS.filter((s) => sectionAllowed(s, keys)).map((s) => {
    if (s.pages) return { ...s, pages: s.pages.filter((p) => pageAllowed(p, keys)) };
    if (s.tabs?.some((t) => t.perm)) return { ...s, tabs: allowedTabs(s.tabs, s, keys) };
    return s;
  });
}

/** Darf diese Adresse geoeffnet werden? */
export function allowed(found: Resolved, keys: string[]): boolean {
  return found.page
    ? pageAllowed(found.page, keys)
    : sectionAllowed(found.section, keys);
}

/**
 * Die erste Seite, die jemand sehen darf. Ziel jeder Weiterleitung.
 *
 * Die markierte Startseite hat Vorrang, aber nur wenn sie erlaubt ist. Sonst
 * landete ein Sprachexperte auf den Auftraegen und damit sofort im 403.
 */
export function firstAllowed(keys: string[]): Resolved | null {
  const start = home();
  if (start && allowed(start, keys)) return start;
  for (const section of allowedSections(keys)) {
    if (!section.pages) return { section, path: section.slug };
    const page = section.pages.find((p) => !p.hidden) ?? section.pages[0];
    if (page) return { section, page, path: `${section.slug}/${page.slug}` };
  }
  return null;
}


