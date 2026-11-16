/** The questions the exercise views send to the chat, in the interface language. */
export function chatPrompts(locale: string) {
  const en = locale === "en";
  return {
    tip: (term: string) => en
      ? `Give me a brief hint for the following question, WITHOUT revealing the answer: "${term}"`
      : `Gib mir einen kurzen Tipp zur folgenden Frage, OHNE die Antwort zu verraten.: „${term}"`,
    termDeep: (term: string) => en
      ? `Explain the term "${term}" in detail. What does it mean, in which contexts is it used, and what are the important relationships?`
      : `Erkläre mir den Begriff „${term}" genauer. Was bedeutet er, in welchem Kontext wird er verwendet und welche Zusammenhänge sind wichtig?`,
    topicDeep: (term: string) => en
      ? `Explain the following topic in more detail: "${term}". What are important details, examples, and connections?`
      : `Erkläre mir folgendes Thema genauer: „${term}". Was sind wichtige Details, Beispiele und Zusammenhänge?`,
  };
}
