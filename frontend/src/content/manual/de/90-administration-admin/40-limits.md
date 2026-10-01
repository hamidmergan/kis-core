# Grenzen

Unter Grenzen stehen alle Obergrenzen für Größe, Umfang und Kontext, in zwei Reitern.

## Material

- **Dienste**: Folien je Screencast (ab Werk 200, mehr Folien heißt vor allem längere Wartezeit,
  ein Screencast bricht nach zwei Stunden ab). Laufende Aufträge je Person (ab Werk 5, zählt über
  alle Dienste, dabei zählen Dienste mit Stimme wie Text in Audio, Podcast und Screencast getrennt
  von den übrigen. -1 heißt unbegrenzt). Aufbewahrte Aufträge je Person (ab Werk 100, die einzige
  Aufräumregel, kommt ein weiterer Auftrag dazu, verschwindet der älteste samt Datei. -1 heißt,
  nur der Plattenplatz begrenzt).
- **KI-Assistent**: Maximale Materialien pro Workspace (ab Werk 50). Maximale Zeichen je Dokument
  (zwischen 30.000 und 500.000, gezählt nach dem Einlesen, ein zu großes Dokument gilt als
  fehlgeschlagen statt gekürzt zu werden. Bei 500.000 passt jedes Dokument allein auch in Podcast,
  Präsentation und Zusammenfassung).
- **Gemeinsam**: Größe einer Datei in MB (ab Werk 500, gilt für jede hochgeladene Datei, beim
  Podcast für alle Dateien eines Auftrags zusammen). Maximale Seiten pro Material (ab Werk 200,
  gilt für Materialien im Workspace und für Podcast, Zusammenfassung und Übersetzung, Medien und
  Screencast sind nicht betroffen). Länge einer Aufnahme in Minuten (ab Werk 100, längere werden
  automatisch in Stücke geschnitten und einzeln erkannt).

## Kontext

- **Chat Kontext-Budget für Überblicksfragen** und **für gezielte Fragen**: wie viel Text der
  KI-Assistent Francis je Fragetyp ins Modell gibt, in Zeichen, mit Anzeige in Token.
- **Kontext-Budget der Tools**: wie viel Text aus den Materialien die Tools ins Modell geben
  dürfen. Mindmap, Podcast, Zeitplan und Datentabelle schöpfen den Wert aus, Karteikarten,
  Lernkarten, Quiz, Wortschatz- und Grammatikübung nehmen sich nur so viel, wie die bestellte
  Anzahl Aufgaben braucht. Schafft das eingestellte Modell diesen Wert nicht, lehnt es den Auftrag
  ab, dann hilft nur, den Wert zu senken.
