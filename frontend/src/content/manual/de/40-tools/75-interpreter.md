# Dolmetscher

Zwei Sprachen, ein Gespräch. Jede Seite hat ein eigenes Feld in ihrer Sprache, daneben läuft die
Übersetzung mit. Alles bleibt im Verlauf.

![Der Dolmetscher mit zwei Sprachen](/manual/{lang}/tool-interpreter.png)

## So läuft ein Gespräch

- **Sprechen** startet die Aufnahme, **Fertig** beendet sie, oder die andere Seite drückt Sprechen
  und übernimmt das Wort. Schon während Sie sprechen, läuft eine Live-Übersetzung mit, nach
  Fertig wartet der Satz auf die vollständige Erkennung.
- **Tippen** geht genauso, Enter oder Übersetzen schickt den Satz ab.
- **Korrigieren**: Erkennt die KI ein Wort falsch, ändern Sie den Satz direkt im Feld.
- **Seiten tauschen** dreht die Sprachen um. Aktuell gibt es Deutsch und Englisch.
- **Namen**: Person 1 und Person 2 lassen sich umbenennen, bis 80 Zeichen.

## Grenzen

- **Eine Aufnahme** endet nach 5 Minuten von selbst, ab 4:30 Minuten sagt die Karte, dass gleich
  Schluss ist.
- **Ein getippter Satz** darf 2.000 Zeichen haben.
- **Ein Gespräch** endet bei 20.000 Zeichen. Gezählt wird nur das Gesagte und Getippte, nicht die
  Übersetzung. Ab 18.000 Zeichen warnt die Seite. Ein volles Gespräch bleibt lesbar, Neues
  Gespräch macht sofort weiter.
- **Frühere Gespräche**: Jedes begonnene Gespräch wird gespeichert, die letzten 100 je Konto.
  Kommt ein neues dazu, fällt das am längsten unbenutzte heraus.

## Einstellungen

Hinter dem Zahnrad wählen Sie den KI-Anbieter für die Spracherkennung und den für die Übersetzung,
dazu bis zu 3 Glossare. Ton und Text gehen nur an die hier gewählten Anbieter, die
Spracherkennung des Browsers wird nicht genutzt.

## Protokoll und frühere Gespräche

- **Protokoll** zeigt beide Sprachen in der Reihenfolge des Gesprächs und lädt sie als Textdatei
  herunter, mit Uhrzeit und Name vor jedem Satz.
- **Frühere Gespräche** öffnet ein gespeichertes Gespräch zum Nachlesen oder Weiterführen, oder
  löscht es.

Der Dolmetscher erzeugt keine Aufträge und hat kein Kontingent.
