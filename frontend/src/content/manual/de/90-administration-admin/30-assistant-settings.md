# KI-Assistent einstellen

Unter KI-Assistent legen Sie fest, wie Material eingelesen wird und wie der Sprachtrainer
arbeitet, in zwei Bereichen.

## Materialien

- **OCR für Scans und Bild-Seiten**: an heißt, bild- oder scanlastige Seiten laufen beim Einlesen
  durch Texterkennung, das kostet pro Seite einen eigenen Aufruf und dauert länger. Aus heißt
  schneller und günstiger, solche Seiten bleiben dann aber in der Suche leer.
- **Sprache der Tools**: in welcher Sprache Karteikarten, Quiz, Datentabelle und Mindmap
  geschrieben werden. Der Sprachtrainer folgt dem nicht, er bleibt auf Deutsch.
- **Alle Materialien neu indexieren**: berechnet die Embeddings aller Workspaces mit dem
  aktuellen Anbieter neu, nötig nach einem Wechsel des Einbettungsmodells. Braucht vorher den
  Wartungsmodus unter System. Ein Hinweis zeigt, wie viele Workspaces noch mit einem anderen
  Modell indexiert sind.
- **Vorräte leeren**: Aufgabensätze und Zeitplan-Auswertungen, die beim Benutzen entstehen und an
  der Quelle hängen statt am Workspace, lassen sich hier plattformweit wegwerfen. Fertige
  Aufgabensätze, Fortschritt und eingetragene Termine bleiben stehen, nur das im Hintergrund
  Vorbereitete geht verloren und entsteht bei Bedarf neu.

## Sprachniveau

Zwei Reiter.

**Einstufung**

- **Sprachtrainer**: der Schalter für die ganze Plattform. Aus heißt, niemand wird gefragt und der
  Trainer taucht nirgendwo auf. Getroffene Entscheidungen und Niveaus bleiben dabei gespeichert
  und gelten wieder, sobald Sie einschalten. Wer den Trainer tatsächlich sieht, braucht zusätzlich
  ein eigenes Recht in der Rechtematrix, das keine System-Rolle von Haus aus trägt.
- **Fragen im Sprach-Test**: der Fragenkatalog, ab Werk 12 Fragen. Jede Frage ist Auswahl
  (anklicken, mit mindestens einer richtigen Antwort) oder Freitext (selbst tippen). Freitext mit
  eingetragener Lösung prüft der Code wortgenau, ohne Lösung beurteilt die KI die Antwort am Ende.
  Mindestens 2 Freitextfragen ohne Lösung sind Pflicht, nur über sie bekommt die KI eine echte
  Textprobe. Der Test selbst läuft ohne einen einzigen KI-Aufruf, nur die Einstufung am Ende
  braucht einen. Der ganze Fragensatz lässt sich auch einmal von der KI schreiben und danach
  durchsehen.

**KI-Verhalten**

- **Stufen A1 bis C2**: Beschreibung und Beispielsätze je Stufe, die Grundlage für Einstufung und
  für die angepassten Antworten im Chat.
- **Erweitert**: die Prompt-Texte für Test, Chat, Dienste und Tools, nur mit entsprechenden
  Kenntnissen ändern.
