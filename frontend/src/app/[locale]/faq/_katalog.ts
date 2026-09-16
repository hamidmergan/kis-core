/** Which questions the FAQ shows and in which group, the texts themselves live in the message files. */
export const FAQ_GRUPPEN = [
  { key: "basics", items: ["whatIsKis", "vsChatgpt", "moduleServiceTool", "costs"] },
  { key: "data", items: ["gdpr", "hosting", "models", "whoSees", "upload", "afterPilot"] },
  { key: "francis", items: ["notFound", "generalQuestions", "trust", "language"] },
  { key: "operation", items: ["duration", "missingService", "studentView", "bugReport"] },
] as const;

export type FaqGruppe = (typeof FAQ_GRUPPEN)[number];

/** Every question key in reading order. */
export function faqSchluessel(): string[] {
  return FAQ_GRUPPEN.flatMap((gruppe) => [...gruppe.items]);
}
