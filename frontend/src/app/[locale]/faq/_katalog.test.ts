import { describe, expect, it } from "vitest";

import de from "../../../../messages/de.json";
import en from "../../../../messages/en.json";
import { FAQ_GRUPPEN, faqSchluessel } from "./_katalog";

/** A question without its text would render as a bare key on the page. */

type Eintrag = { q?: string; a?: string; todo?: string };

function eintraege(messages: Record<string, unknown>): Record<string, Eintrag> {
  const faq = messages.faq as { items?: Record<string, Eintrag> } | undefined;
  return faq?.items ?? {};
}

describe("FAQ-Katalog", () => {
  it("nennt jeden Schluessel nur einmal", () => {
    const alle = faqSchluessel();
    expect(new Set(alle).size).toBe(alle.length);
  });

  it("hat zu jeder Gruppe eine Ueberschrift in beiden Sprachen", () => {
    for (const sprache of [de, en] as unknown as Record<string, unknown>[]) {
      const gruppen = (sprache.faq as { groups?: Record<string, string> }).groups ?? {};
      for (const gruppe of FAQ_GRUPPEN) expect(gruppen[gruppe.key]).toBeTruthy();
    }
  });

  it("hat zu jeder Frage einen Text in beiden Sprachen", () => {
    for (const sprache of [de, en] as unknown as Record<string, unknown>[]) {
      const items = eintraege(sprache);
      for (const schluessel of faqSchluessel()) expect(items[schluessel]?.q).toBeTruthy();
    }
  });

  it("gibt jeder Frage eine Antwort oder einen Platzhalter", () => {
    for (const sprache of [de, en] as unknown as Record<string, unknown>[]) {
      const items = eintraege(sprache);
      for (const schluessel of faqSchluessel()) {
        const eintrag = items[schluessel];
        expect(Boolean(eintrag?.a || eintrag?.todo), schluessel).toBe(true);
      }
    }
  });

  it("kennt keine Frage, die auf der Seite nicht vorkommt", () => {
    const erwartet = new Set(faqSchluessel());
    for (const sprache of [de, en] as unknown as Record<string, unknown>[]) {
      for (const schluessel of Object.keys(eintraege(sprache))) {
        expect(erwartet.has(schluessel), schluessel).toBe(true);
      }
    }
  });
});
