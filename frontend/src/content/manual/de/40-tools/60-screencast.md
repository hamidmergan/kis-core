# Screencast

Macht aus einer PowerPoint-Datei ein vertontes Video, auf Wunsch in einer anderen Sprache.

![Der Dienst Screencast](/manual/{lang}/tool-screencast.png)

## Die acht Schritte

1. **Upload**: eine .pptx-Datei mit ab Werk höchstens 50 Folien. Hier fällt die Sprachwahl:
   Zielsprache für die Übersetzung oder, mit Übersetzung überspringen, die Sprache der
   Sprechtexte. Dazu Glossar und Übersetzungsanbieter. Die Ausgangssprache wird erkannt.
2. **Übersetzen** läuft von allein, beim Überspringen entfällt der Schritt.
3. **Prüfen**: die übersetzte oder übernommene PPTX herunterladen, in PowerPoint korrigieren und
   wieder hochladen. Die Folienzahl muss gleich bleiben. Folien, deren Text sich beim Übersetzen
   nicht geändert hat, sind markiert.
4. **Anweisungen**: woher die Sprechtexte kommen. KI-Generierung aus den Folien, Manuell
   eingeben, Skript importieren als JSON-Liste oder Aus den Sprechernotizen der Datei.
5. **Skripte**: jeden Text prüfen, ändern oder mit Francis überarbeiten. Das ist der Schritt, an
   dem sich die Qualität entscheidet. Alle Sprechtexte zusammen dürfen 100.000 Zeichen haben.
6. **Einstellungen**: Anbieter und Stimme, Geschwindigkeit von 0,7-fach bis 1,2-fach, Pause
   zwischen den Folien von 0 s bis 3 s, Bildqualität und Untertitel einbauen.
7. **Rendern**: Vertonung und Videoproduktion, läuft im Hintergrund.
8. **Fertig**: MP4 oder alles als ZIP herunterladen.

## Zusätzliches Material

Bei der KI-Generierung können Sie Material mitgeben, aus dem passende Stellen in die Sprechtexte
der einzelnen Folien einfließen: bis zu 10 Dateien oder Workspace-Materialien, zusammen höchstens
500.000 Zeichen. Es gelten dieselben Grenzen wie bei der Zusammenfassung.

## Untertitel

Mit Untertitel einbauen wird der gesprochene Text erkannt und als Spur ins Video gelegt, im Player
mit CC an und aus schaltbar. Das Rendern dauert dadurch etwas länger.

## Nach dem Rendern

- **Einzelne Folien neu vertonen**: Sie haken die Folien an, die neu gesprochen werden sollen,
  etwa nach einem geänderten Text oder mit einer anderen Stimme. Alle anderen behalten ihren Ton.
- **Wiederholen** nach einem Fehler behält fertige Clips und Ton, nur der Rest wird neu gemacht.
- **Angehalten**: nach mehreren gescheiterten Anläufen wartet der Auftrag auf Weiter.

## Die Demo

Demo ansehen im ersten Schritt öffnet den Dienst mit einem vorbereiteten Foliensatz. Alle
Schritte und Einstellungen lassen sich ausprobieren, eigene Dateien lassen sich nicht hochladen,
und das Ergebnis ist immer das vorbereitete Beispielvideo.

## Wie lange es dauert

Der weitaus größte Teil der Wartezeit geht auf die Vertonung. Der Auftrag läuft im Hintergrund,
das Ergebnis wartet unter Jobs. Wie viele Aufträge Sie gleichzeitig offen haben dürfen, steht im
Überblick der Dienste.
