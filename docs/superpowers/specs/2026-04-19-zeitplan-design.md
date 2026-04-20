# Zeitplan — Design Spec

**Datum:** 2026-04-19
**Branch:** `feat/meilensteine`
**Status:** Abgestimmt, bereit für Implementierungsplan

## Zweck

Neue Studio-Ansicht neben "Statistik", die aus hochgeladenen Quellen datierte Ereignisse und Fristen extrahiert und als vertikalen Zeitstrahl darstellt. Nutzer kann Einträge abhaken, editieren, manuell hinzufügen und löschen.

## Scope

**Drin:**
- LLM-basierte Extraktion von Datumsereignissen aus 1..n ausgewählten Quellen
- Zwei semantische Typen: `deadline` (muss bis Datum erledigt sein) und `termin` (Ereignis am Datum)
- Anzeige als vertikaler Zeitstrahl, Einträge abwechselnd links/rechts
- Checkbox zum Abhaken
- Edit-Mode: manuell erstellen, bearbeiten, einzeln löschen
- Reset-Funktion: alle Einträge löschen + Quellen-Tracker leeren
- "Datum offen"-Sektion für Einträge ohne konkretes Datum

**Draußen:**
- Kalender-Sync, Reminder, Push-Notifications
- Automatische Extraktion bei Upload (nur manueller Trigger)
- Automatische Deduplizierung zwischen Quellen
- Badges, Animationen für neu hinzugefügte Einträge

## Plazierung in der UI

- Neuer Studio-Tab neben "Statistik": **Tools / Sprachtraining / Glossar / Notizen / Statistik / Zeitplan**
- Tab-Label: "Zeitplan"
- Pro Workspace (Modul) genau ein Zeitplan

## Datenmodell

### Tabelle `kia_zeitplan_entries`

```sql
CREATE TABLE kia_zeitplan_entries (
    id           SERIAL PRIMARY KEY,
    module_id    INTEGER NOT NULL REFERENCES kia_modules(id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL,
    type         TEXT NOT NULL CHECK (type IN ('deadline', 'termin')),
    title        TEXT NOT NULL,
    description  TEXT,
    due_date     DATE,
    due_time     TIME,
    is_optional  BOOLEAN NOT NULL DEFAULT FALSE,
    is_checked   BOOLEAN NOT NULL DEFAULT FALSE,
    checked_at   TIMESTAMP,
    origin       TEXT NOT NULL CHECK (origin IN ('llm', 'manual')),
    source_ids   JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_quote    TEXT,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_zeitplan_module_user ON kia_zeitplan_entries(module_id, user_id);
CREATE INDEX idx_zeitplan_due_date ON kia_zeitplan_entries(module_id, user_id, due_date);
```

### Tabelle `kia_zeitplan_processed_sources`

Trackt welche Quellen bereits vom LLM verarbeitet wurden. Eine einmal verarbeitete Quelle wird **niemals** erneut verarbeitet, bis der gesamte Zeitplan gelöscht wird.

```sql
CREATE TABLE kia_zeitplan_processed_sources (
    module_id     INTEGER NOT NULL REFERENCES kia_modules(id) ON DELETE CASCADE,
    user_id       INTEGER NOT NULL,
    source_id     INTEGER NOT NULL REFERENCES kia_sources(id) ON DELETE CASCADE,
    processed_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (module_id, user_id, source_id)
);
```

### Eigenschaften des Modells

- `due_date IS NULL` → Eintrag rendert in Sektion "Datum offen"
- `due_date` gesetzt → Eintrag rendert im Zeitstrahl an zugehöriger Position
- `origin = 'manual'` → `source_ids = []`, `raw_quote = NULL`
- `origin = 'llm'` → `source_ids` enthält mindestens eine Quelle, `raw_quote` enthält Originalzitat

## Backend-API

Alle Routen unter `/ki-assistent/modules/{module_uuid}/zeitplan`:

| Methode | Pfad | Zweck |
|---|---|---|
| `GET` | `/` | Alle Einträge + Liste der bereits verarbeiteten Quellen |
| `POST` | `/generate` | LLM-Extraktion für neue Quellen (Body: `source_ids[]`) |
| `POST` | `/entries` | Manuellen Eintrag anlegen |
| `PUT` | `/entries/{id}` | Eintrag bearbeiten (inkl. Checkbox-Toggle) |
| `DELETE` | `/entries/{id}` | Einzelnen Eintrag löschen |
| `DELETE` | `/` | Alle Einträge löschen + Tracker leeren |

### Generate-Endpoint: Verhalten

1. Nimmt Liste von `source_ids` entgegen
2. Filtert: nur Quellen, die **nicht** in `kia_zeitplan_processed_sources` stehen
3. Extrahiert für jede verbleibende Quelle einzeln via LLM
4. Schreibt neue Einträge in `kia_zeitplan_entries` (append-only, nie überschreiben)
5. Trägt die verarbeiteten Quellen in `kia_zeitplan_processed_sources` ein
6. Gibt die neu hinzugefügten Einträge zurück

Wenn alle übergebenen `source_ids` schon verarbeitet wurden: keine Aktion, leere Antwort.

### Delete-All-Endpoint: Verhalten

1. Löscht alle Einträge (`kia_zeitplan_entries`) für `module_id + user_id`
2. Löscht alle Rows in `kia_zeitplan_processed_sources` für `module_id + user_id`
3. Damit werden alle Quellen wieder "verarbeitbar" im nächsten Generate-Aufruf

## LLM-Extraktion

### Prompt (schematisch)

```
System: Du extrahierst datierte Ereignisse und Fristen aus einem Dokument.

Regeln:
- Extrahiere nur, was explizit im Dokument steht, keine Annahmen
- Typ "deadline": etwas muss bis zu einem Datum erledigt sein (Abgaben, Einreichungen, Zahlungen, Kündigungsfristen)
- Typ "termin": Ereignis findet am Datum statt (Prüfung, Meeting, Vertragsende, Go-Live)
- Wenn Datum nicht eindeutig ist ("nach Absprache", "wird bekanntgegeben"), lasse due_date leer und trage den Original-Wortlaut in description
- Markiere optional=true wenn explizit als "freiwillig", "optional", "nach Wahl" gekennzeichnet
- Trage in raw_quote den unveränderten Originalsatz aus dem Dokument ein (Anti-Halluzinations-Anker)

Output: JSON-Array mit Einträgen.

User: <Dokumenttext>
```

### JSON-Schema der LLM-Antwort

```json
[
  {
    "type": "deadline" | "termin",
    "title": "string",
    "description": "string | null",
    "due_date": "YYYY-MM-DD | null",
    "due_time": "HH:MM | null",
    "is_optional": false,
    "raw_quote": "string"
  }
]
```

### LLM-Client

Verwende denselben KISski-Client wie bestehende Studio-Features (z.B. Datentabelle, Glossar): `get_kisski_client` Dependency aus `src.dependencies`. Langfuse-Observation mit `@observe` wie im restlichen KI-Assistent-Bereich.

### Fehlerbehandlung

- LLM-Call schlägt fehl: gibt HTTP-Fehler zurück, Quelle wird **nicht** als verarbeitet markiert
- LLM gibt invalides JSON: Retry 1x, sonst Fehler, Quelle nicht markiert
- LLM gibt leeres Array: Quelle wird als verarbeitet markiert (keine Einträge ist eine valide Antwort)

## Frontend

### Button-Styles (an bestehenden Konventionen)

- **"Aus Quellen generieren"**: analog zum "Begriffe extrahieren"-Button im `GlossarView` (weißer Background, 1.5px Accent-Border, Accent-Text, `rounded-lg`, Sparkle-Icon vorn). Siehe [GlossarView.tsx:78-88](frontend/src/app/workspaces/[uuid]/_components/GlossarView.tsx#L78-L88).
- **"Bearbeiten"**: Icon-Only runder Button (28x28) im Stil des `DotsThreeVertical` in `GlossarMenu` (Surface-Dim-Background, Muted-Farbe, `PencilSimple`-Icon). Siehe [GlossarView.tsx:24-28](frontend/src/app/workspaces/[uuid]/_components/GlossarView.tsx#L24-L28).

### Komponentenstruktur

```
ZeitplanView (Container, Studio-Tab)
├── ZeitplanHeader (Titel, Generieren-Button, Edit-Icon-Button)
├── GenerateSourcesModal (Quellenauswahl-Dialog)
├── ZeitplanTimeline (vertikaler Zeitstrahl)
│   └── ZeitplanEntry (eine Kachel, inkl. Checkbox und Detail-Popover mit raw_quote)
├── ZeitplanOpenSection (Einträge mit due_date = null)
└── EntryEditModal (Create/Edit, genutzt für manuell und Edit)
```

Datei-Ablage: `frontend/src/app/workspaces/[uuid]/_components/zeitplan/`

### Visuelle Regeln

- Corporate-Farben: Primary `#004261`, Muted `#668DA0`, Border `#B8CDD5`
- Vertikaler Zeitstrahl, Einträge abwechselnd links/rechts
- Mittlere Spalte: Datum + Punkt gestapelt, Punkt sitzt auf der Linie
- Vergangenes: `opacity: .5`, graue Dots
- Heute: blauer Dot mit Pulsation, fette Hervorhebung der Karte
- Zukunft: normale Darstellung
- Abgehakt: grüner Dot, Titel durchgestrichen, grünlicher Hintergrund
- Typ-Badges mit Phosphor-Icons + Farbakzent
- Sektion "Datum offen" unten: max-width 520px, zentriert, neutrale weiße Cards (kein eigener Akzent-Background), Section-Label in Muted-Farbe

### Icons (Phosphor)

| Zweck | Icon |
|---|---|
| Header-Titel | `CalendarBlank` |
| Edit-Button | `PencilSimple` |
| Generieren-Button | `Sparkle` |
| Deadline-Badge | `Warning` |
| Termin-Badge | `MapPin` |
| Optional-Marker | `Star` |
| Checkbox-Haken | `Check` |
| Uhrzeit-Indikator | `Clock` |
| Quellen-Indikator | `File` |
| "Datum offen"-Sektion | `Question` |

### Generieren-Flow (UI)

1. User klickt "Aus Quellen generieren"
2. Modal öffnet sich mit Liste aller Quellen des Moduls
3. Bereits verarbeitete Quellen sind **disabled** (grau, Tooltip "Bereits verarbeitet — löschen und neu generieren um erneut einzubeziehen")
4. User hakt eine oder mehrere unverarbeitete Quellen an
5. Klick auf "Generieren" — Loading-State
6. Neue Einträge werden in Timeline angehängt
7. Toast: "3 neue Einträge hinzugefügt" o.ä.

### Edit-Mode

- Toggle-Button "Bearbeiten" wechselt in Edit-Mode
- In Edit-Mode: jede Karte zeigt Edit-Icon (öffnet Modal) und Delete-Icon (mit Confirm)
- Button "Neuer Eintrag" oben
- Button "Alles löschen" unten rot, mit Confirm-Modal
- "Fertig"-Button beendet Edit-Mode

### Checkbox-Verhalten

- Click auf Checkbox togglet `is_checked`
- Optimistic Update im Frontend, PUT-Call auf `/entries/{id}`
- Abgehakte Einträge bleiben an ihrer Position (keine Sortierung nach Status)

## UX-Anti-Halluzinations-Maßnahmen

- Jeder LLM-Eintrag zeigt Quellendateiname(n)
- Klick auf Eintrag öffnet Detail-Popup mit Originalzitat (`raw_quote`)
- User kann LLM-Einträge editieren oder löschen
- Keine Auto-Aktualisierung bestehender Einträge, niemals

## Eiserne Regeln

1. Eine einmal LLM-verarbeitete Quelle wird **nie** automatisch erneut verarbeitet
2. Bestehende Einträge werden **nie** durch Generate überschrieben oder entfernt
3. User-Edits an LLM-Einträgen bleiben erhalten, auch wenn die Ursprungsquelle erneut ausgewählt würde (technisch verhindert durch Regel 1)
4. Einzige Rücksetz-Möglichkeit: "Alles löschen"-Button im Edit-Mode

## Bewusst vertagt (spätere Versionen)

- Automatische Deduplizierung gleicher Deadlines aus mehreren Quellen
- Reminder-Mails vor Deadline
- Export als `.ics`-Kalenderdatei
- Drag & Drop zum Neuanordnen manueller Einträge
- Wiederkehrende Termine
- Filter- oder Suchleiste

## Offene Punkte

Keine. Alle Entscheidungen abgestimmt.
