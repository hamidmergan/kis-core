# Anbieter und Modelle

Unter Anbieter & Modelle liegen die Zugänge zu den KI-Anbietern und die Frage, welche Funktion
welches Modell nutzt, in zwei Reitern.

## Anbieter

Ein Anbieter braucht einen Namen, ein Protokoll (OpenAI-kompatibel, DeepL oder Docling, nach dem
Anlegen fest), eine Base-URL und meist einen API-Key. Nach dem Speichern zeigt KIS nur noch die
letzten sechs Zeichen des Schlüssels.

- **Fähigkeiten**: leer lassen heißt, KIS ermittelt sie nach dem Speichern selbst.
- **Gleichzeitige Aufrufe**: je Bereich (LLM, Spracherkennung, Stimmen, Bilder, Einbettungen,
  Texterkennung) eine eigene Obergrenze, leer heißt ohne Grenze. Der Chat mit Francis zählt dabei
  nicht mit, Bildanalyse zählt beim LLM mit.
- **Stimmen**: bei einem TTS-fähigen Anbieter lassen sich Stimmen automatisch laden oder von Hand
  eintragen, mit Sprache und Beschreibung, zum Vorhören.
- Je Zeile: Aktivieren oder Deaktivieren, Erreichbarkeit prüfen, Bearbeiten, Löschen (warnt, welche
  Funktionen danach fehlen würden). Über das Menü Export/Import (der Schlüssel bleibt
  verschlüsselt) und Alles löschen.
- Unter jedem Anbieter steht das Kontextfenster je Modell in Token, automatisch gemessen. Eine von
  Hand eingetragene Zahl gilt, ein geleertes Feld misst neu.

## Funktionen

Jede Funktion (Chat, Embeddings, Bildanalyse, Bildgenerierung, Bild-Edit, OCR, Speech-to-Text,
Text-to-Speech, Dokumenten-Übersetzung, Transkript-Übersetzung) zeigt alle passenden Anbieter,
jeder mit eigenem Modellfeld.

- **Erste Wahl**: der Stern direkt am Anbieter, braucht vorher ein eingetragenes Modell. Gilt für
  alle Funktionen, bei Text-to-Speech legt er zusätzlich die Standardstimme fest.
- **Rückfall**: je Funktion wählbar. Antwortet die erste Wahl nicht oder weist den Aufruf ab, geht
  derselbe Aufruf an den Rückfall. Infrage kommen nur aktive Anbieter mit OpenAI-kompatibler
  Schnittstelle und eingetragenem Modell, bei Embeddings nur mit demselben Modell, bei
  Text-to-Speech nur mit eigenen Stimmen. Bei Text-to-Speech wechselt die Stimme dabei nie
  innerhalb eines laufenden Auftrags, höchstens beim nächsten. Ohne eingestellten Rückfall wird
  nicht gewechselt.
- Läuft der erste Anbieter beim LLM voll, weicht ein Aufruf von selbst auf den nächsten Anbieter
  mit Modell aus, in der Reihenfolge der Liste. Bilder und Stimmen weichen nie aus.
- **Feinjustierung** (Temperatur, top_p): hinter einem Haken verborgen, nur bei chatartigen
  Funktionen.
- Bei Text-to-Speech, Bildanalyse, Bildgenerierung, Bild-Edit und Dokumenten-Übersetzung wählt die
  Person den Anbieter selbst im Dienst. Bei Podcast, Präsentation und Zusammenfassung wählt sie
  einen erreichbaren Anbieter mit Modell, der Stern ist dabei die Vorgabe.
- Je Zeile ein Blitz-Symbol Auswahl testen, dazu Alle nacheinander testen. Eine Vorschau oder einen
  Testbetrieb gibt es nicht, jede Änderung gilt sofort für alle.
