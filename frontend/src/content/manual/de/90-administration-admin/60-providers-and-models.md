# Anbieter und Modelle

Unter Anbieter & Modelle liegen die Zugänge zu den KI-Anbietern und die Frage, welche Funktion
welches Modell nutzt, in zwei Reitern.

## Anbieter

Ein Anbieter braucht einen Namen, ein Protokoll, eine Adresse und meist einen Schlüssel. Nach dem
Speichern zeigt KIS nur noch die letzten sechs Zeichen des Schlüssels. Dazu lässt sich die Zahl
gleichzeitiger Aufrufe je Bereich begrenzen, und bei einem Stimmanbieter die Stimmen laden oder
von Hand eintragen. Je Zeile: aktivieren, Erreichbarkeit prüfen, bearbeiten, löschen, dazu
Export/Import und Alles löschen im Menü.

## Funktionen

Jede Funktion (Chat, Bildanalyse, Bildgenerierung, Texterkennung, Spracherkennung,
Text-to-Speech, Übersetzung, ...) zeigt alle passenden Anbieter mit eigenem Modellfeld.

- **Erste Wahl**: der Stern direkt am Anbieter, bei Text-to-Speech legt er zusätzlich die
  Standardstimme fest.
- **Rückfall**: springt ein, wenn die erste Wahl nicht antwortet oder ablehnt. Bei Text-to-Speech
  wechselt die Stimme dabei nie innerhalb eines laufenden Auftrags.
- Läuft der erste Anbieter beim LLM voll, weicht ein Aufruf von selbst auf den nächsten mit Modell
  aus. Bilder und Stimmen weichen nie aus.
- Bei einigen Funktionen wählt die Person den Anbieter selbst im Dienst, bei Podcast,
  Präsentation und Zusammenfassung ebenso, der Stern ist dort nur die Vorgabe.
- Je Zeile ein Test der aktuellen Auswahl. Jede Änderung gilt sofort für alle, eine Vorschau oder
  einen Testbetrieb gibt es nicht.
