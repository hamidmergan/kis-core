# Settings-Konzept — Design Spec

**Date:** 2026-04-30
**Branch:** `feat/hilde-mascot` (folgt: dedizierter Branch)
**Scope:** Globale User-Settings (Header) + Workspace-Settings (AIA), inkl. Transkript-Übersetzungs-Modus, Theme, Sprache. Admin-Panel bleibt unberührt.

---

## Goals

1. Klare Trennung: globale User-Settings (Header) vs. Workspace-Settings (AIA-Dropdown)
2. Header-Settings-Modal entfernen — direkte Controls (Sprache-Switch, Theme-Toggle) im Header
3. Sprache wandert vom (deaktivierten) AIA-Feld in den Header und gilt global pro User
4. Theme-Toggle als Platzhalter einbauen (Light/Dark, Klick = Switch)
5. Hilde-Toggle wandert ins AIA-Settings-Dropdown
6. Transkript-Übersetzung pro Workspace konfigurierbar: `off` / `auto` / `manual` (default `manual`)
7. Source-Liste bekommt "Ins Englische übersetzen"-Button (für `manual`-Workspaces, Lecturer-only)

## Non-Goals

- Volles UI-i18n (Übersetzung der gesamten Oberfläche) — `chat_lang` steuert weiterhin nur Tool-Outputs/Prompts; UI-Strings bleiben deutsch
- Funktionale Dark-Mode-Implementierung — nur Toggle-UI + persistente User-Pref, CSS-Variablen-Set für `[data-theme="dark"]` ist eigenes Folge-Projekt
- Admin-Settings-Reorganisation — Admin-Panel bleibt wie heute
- Job-fertig-Sound, Reduced-Motion, Schriftgröße, TTS-Stimme, Default-Quellen-Auswahl — verschoben (siehe Open Items)
- Per-User-Override der Workspace-weiten Übersetzung — Workspace-weit ist Workspace-weit

---

## Rollen

Bestehend, kein Change:

| Code | UI-DE | Bedeutung |
|---|---|---|
| `lecturer` (`users.role`) | Dozent:in | Kann Workspaces erstellen/besitzen |
| `student` (`users.role`) | Studierende:r | Kann nur teilnehmen |
| `is_admin` (Flag) | Admin | Orthogonal — alles erlaubt; sieht zusätzlich Admin-Panel |

"Owner" = `lecturer`, der den Workspace via `aia_workspaces.user_id` besitzt. `isLecturer`-Check in [page.tsx:333](frontend/src/app/workspace/[uuid]/page.tsx#L333) bleibt das Gating-Kriterium für Owner-Settings.

---

## Settings-Matrix

| Setting | Wo | Scope | Default | Dozent:in | Studierende:r |
|---|---|---|---|---|---|
| Sprache (DE/EN) — **Platzhalter** | Header-Dropdown | User | `de` | ✅ | ✅ |
| Theme (Sun/Moon) — **Platzhalter** | Header-Icon | User | `light` | ✅ | ✅ |
| Hilde-Maskottchen | AIA-Settings | User (global) | an | ✅ | ✅ |
| Studio anzeigen | AIA-Settings | User × Workspace | an | ✅ | ✅ |
| Sprachtraining-Tab | AIA-Settings | User × Workspace | aus | ✅ | ✅ |
| Header ausblenden | AIA-Settings | User × Workspace | aus | ✅ | ❌ unsichtbar |
| Transkript-Übersetzung | AIA-Settings | Workspace (Owner) | `manual` | ✅ Owner | ❌ unsichtbar |

**"Platzhalter"** = UI-Element existiert im Header, hat aber keine funktionale Wirkung in dieser Iteration (kein localStorage, keine Propagation). Reine Sicht-Vorbereitung.

Scope-Lese-Hilfe:
- **User** = ein Wert pro User, gilt überall (localStorage)
- **User × Workspace** = pro User pro Workspace, bestehende Tabelle `aia_user_settings`
- **Workspace** = ein Wert für den ganzen Workspace, neue Spalte in `aia_workspaces`, nur Owner sichtbar

---

## Header-Änderungen

### Entfernt

- [`frontend/src/components/layout/HeaderSettings.tsx`](frontend/src/components/layout/HeaderSettings.tsx) — komplette Datei weg (Modal mit Hilde-Toggle)
- Mount-Punkte in [`Header.tsx:54,58`](frontend/src/components/layout/Header.tsx#L54-L58) und [`HeaderMobileMenu.tsx`](frontend/src/components/layout/HeaderMobileMenu.tsx) entfernen

### Neu (Platzhalter)

- `frontend/src/components/layout/HeaderLanguageSwitch.tsx` — Sprache DE/EN als kompaktes Dropdown, **nicht funktional** (lokaler `useState`, keine Persistenz, keine Propagation)
- `frontend/src/components/layout/HeaderThemeToggle.tsx` — Sun/Moon Icon-Toggle, **nicht funktional** (lokaler `useState`, keine Persistenz, kein `data-theme`)
- Hooks `useUiLang.ts` / `useTheme.ts` werden in dieser Iteration **nicht** angelegt — folgen wenn die Settings echt werden

### Header-Layout

**Vorher:**
```
[ KIS DEV ]                          [🔔 Jobs] [⚙ Einstellungen] [👤 Admin] [↩ Abmelden]
```

**Nachher (Sprache + Theme ersetzen den Einstellungen-Slot 1:1, beide mit Icon analog zu den Nachbarn):**
```
[ KIS DEV ]                          [🟦Jobs] [🌐 DE ▾] [☀ Hell]   [👤 Admin] [↩ Abmelden]
```

**Icons (Phosphor, `weight="bold"` outline-only laut Memory-Rule):**
- `HeaderLanguageSwitch`: `Globe` + Text `DE`/`EN` + `CaretDown` — analog zu allen Header-Buttons (Icon + Text)
- `HeaderThemeToggle`: `Sun` (light) ↔ `Moon` (dark) + Text `Hell`/`Dunkel`

**Position:** Genau dort, wo heute der "Einstellungen"-Button (Gear) sitzt — zwischen `JobsPanel` und `Admin`-Link. Reihenfolge: `HeaderLanguageSwitch` → `HeaderThemeToggle`. Beide nutzen das gleiche `btn-on-dark`-Sizing wie die Nachbar-Buttons (`h-9 px-3 rounded-full` bzw. `w-10 h-10` mobile-only).

Konkrete Mount-Stellen in [`Header.tsx`](frontend/src/components/layout/Header.tsx):
- Zeile 54 (`<div className="sm:hidden">…HeaderSettings…`) → entfernen, Mobile geht über `HeaderMobileMenu`
- Zeile 58 (`<HeaderSettings />` zwischen `JobsPanel` und `isAdmin`-Block) → ersetzen durch:
  ```tsx
  <HeaderLanguageSwitch />
  <HeaderThemeToggle />
  ```

**Mobile** ([`HeaderMobileMenu`](frontend/src/components/layout/HeaderMobileMenu.tsx)): Sprache + Theme erscheinen als zwei Einträge oben im Drawer (auch als Platzhalter, gleiche Components mit `mobile`-Variante oder direkt als Listen-Items im Drawer).

### `HeaderLanguageSwitch` — Component-Spec (Platzhalter)

**Visual:**
- Closed: `[ DE ▾ ]` — `btn-on-dark`-Style (transparent, weißer Text, hover dunkler)
- Open: weißes Panel rechts-aligned unter dem Trigger, kb-Border, Phosphor `Check` für ausgewählten Wert

**Logik (Platzhalter):**
- A11y: `role="combobox"`, `aria-expanded`, `aria-haspopup="listbox"` — analog [`Select.tsx`](frontend/src/components/ui/Select.tsx)
- Keyboard: `↑/↓` navigieren, `Enter`/`Space` committen, `Esc` schließen, `Tab` schließt
- Click-outside schließt
- Werte: `de` | `en`, lokaler `useState` mit Default `de`
- **Keine Persistenz**, **keine Propagation** in `chatLang` o.Ä.
- Bestehendes (deaktiviertes) Sprache-Feld in [`SettingsMenu.tsx:34-56`](frontend/src/app/workspace/[uuid]/_components/layout/SettingsMenu.tsx#L34-L56) wird **trotzdem entfernt** (war ohnehin disabled, alle bisherigen Lese-Pfade lesen weiterhin das DB-Feld bis zur echten Migration)
- `aia_user_settings.chat_lang` und der `chat_lang`-Lese-/Schreib-Pfad **bleiben unverändert** in dieser Iteration — Drop und Migration erst wenn der Header-Switch echt wird

### `HeaderThemeToggle` — Component-Spec (Platzhalter)

**Visual:**
- Light-Mode: Phosphor `Sun` Icon (weight=`bold`, outline-only laut Memory-Rule)
- Dark-Mode: Phosphor `Moon` Icon
- Button-Style: `btn-on-dark`, gleiches Sizing wie andere Header-Buttons (h-9, rounded-full)
- Tooltip: "Heller Modus" / "Dunkler Modus"

**Logik (Platzhalter):**
- Klick togglet `light ↔ dark` nur im lokalen `useState`
- **Keine Persistenz**, **kein** `localStorage`, **kein** `data-theme`-Attribut
- Default: `light`
- Wirkung: nur das Icon wechselt — sichtbares Demo, sonst nichts

---

## AIA-Workspace-Settings-Änderungen

### Datei: [`SettingsMenu.tsx`](frontend/src/app/workspace/[uuid]/_components/layout/SettingsMenu.tsx)

Neue Reihenfolge im Dropdown (oben → unten):

1. **Hilde-Maskottchen** (User global, alle User) — Toggle, ersetzt den Header-Modal-Eintrag; nutzt weiterhin [`useHildePref`](frontend/src/hooks/useHildePref.ts) (localStorage), gilt damit über alle Workspaces hinweg
2. **Studio anzeigen** (User × WS, alle User) — bestehend, unverändert
3. **Sprachtraining-Tab** (User × WS, alle User) — bestehend, abhängig von Studio
4. **Header ausblenden** (User × WS, nur Lecturer) — bestehend, unverändert
5. **Transkript-Übersetzung** (Workspace, nur Owner) — neu, drei Radio-Buttons

Entfernt: das (deaktivierte) Sprache-Feld.

### `SettingsMenu`-Props (neu)

```ts
interface SettingsMenuProps {
  // entfernt: chatLang
  // Hilde wird NICHT als Prop reingereicht — SettingsMenu nutzt useHildePref() direkt (global, kein Workspace-Scope)
  studioEnabled: boolean;
  onToggleStudio: () => void;
  language_trainingActive: boolean;
  onToggleLanguageTraining: () => void;
  isLecturer: boolean;          // weiterhin true = Owner-Sicht
  isOwner: boolean;             // neu: lecturer UND auth.user_id === workspace.user_id
  hideHeader: boolean;
  onToggleHideHeader: () => void;
  translationMode: "off" | "auto" | "manual";
  onChangeTranslationMode: (m: "off" | "auto" | "manual") => void;
}
```

`isOwner` ist enger als `isLecturer`: ein Lecturer, der **nicht** Owner des Workspaces ist (z.B. eingeladener Co-Dozent), darf den Translation-Mode nicht ändern. Falls Co-Dozenten-Konzept noch nicht existiert: `isOwner` zunächst gleich `isLecturer && workspace.user_id === auth.user_id`.

### Translation-Mode-UI (Owner-Sicht)

```
Transkript-Übersetzung (Englisch)
Wirkt auf neue Audio-/Video-Quellen in diesem Workspace.

  ( ) Aus       Keine englische Übersetzung erzeugen
  ( ) Auto      Automatisch nach dem Indexieren übersetzen
  (•) Manuell   Nur über Button in der Quellen-Liste
```

3 Radios in einem Block, kb-Border. Speichert beim Klick (PATCH `/api/ai-assistant/workspaces/{uuid}`).

---

## Backend-Änderungen

### DB-Schema

**`aia_workspaces`** — neue Spalte:

```sql
ALTER TABLE aia_workspaces
  ADD COLUMN IF NOT EXISTS transcript_translation_mode TEXT NOT NULL DEFAULT 'manual';
-- CHECK constraint: ('off', 'auto', 'manual')
ALTER TABLE aia_workspaces
  ADD CONSTRAINT IF NOT EXISTS aia_workspaces_translation_mode_check
  CHECK (transcript_translation_mode IN ('off', 'auto', 'manual'));
```

**`aia_user_settings`** — keine Änderung in dieser Iteration:
- `chat_lang` bleibt (Header-Switch ist Platzhalter, propagiert nicht — alte Pfade bleiben aktiv)
- Kein `hilde_enabled` (Hilde bleibt global per localStorage, nicht workspace-scoped)

### API

**Workspace-Detail-Endpoint** — Response erweitern:
```python
{
  ...,
  "transcript_translation_mode": "off" | "auto" | "manual"
}
```

**Workspace-Update-Endpoint** — neuer akzeptierter Patch-Key:
```python
PATCH /api/ai-assistant/workspaces/{uuid}
{ "transcript_translation_mode": "auto" }
```
Server prüft: nur Owner darf setzen (Reuse von bestehender Owner-Check-Logik in `routes/workspaces.py`).

**Settings-Endpoint** ([`useWorkspaceInit.ts:55`](frontend/src/app/workspace/[uuid]/_hooks/useWorkspaceInit.ts#L55)):
- Keine Änderung in dieser Iteration (`chat_lang` bleibt; kein `hilde_enabled`)

**Manuelle-Übersetzung-Endpoint** — neu:
```python
POST /api/ai-assistant/sources/{source_uuid}/translate-en
```
- Owner-Only
- Triggert `run_translate_transcript_en.delay(source_uuid, provider)` mit Provider aus globalen `settings`-Tabelle (wie heute)
- Idempotent: prüft `file_exists(en_key)` (existiert schon in [`ingestion.py:197`](backend/src/features/ai_assistant/tasks/ingestion.py#L197))

### Ingest-Logik anpassen

[`ingestion.py:162-170`](backend/src/features/ai_assistant/tasks/ingestion.py#L162-L170):

```python
if _en_translation_pending:
    workspace = db.get_aia_workspace_by_id(workspace_id)
    mode = workspace.get("transcript_translation_mode", "manual")
    if mode == "auto":
        translation_provider = db.get_setting("transcript_translation_provider", "llm")
        run_translate_transcript_en.delay(source_uuid, translation_provider)
        logger.info("KI Tutor: dispatched EN translation for {} (provider={})", source_uuid, translation_provider)
    elif mode == "off":
        logger.info("KI Tutor: EN translation skipped for {} (workspace mode=off)", source_uuid)
    else:  # manual
        logger.info("KI Tutor: EN translation deferred for {} (workspace mode=manual)", source_uuid)
```

---

## Frontend-Änderungen

### Source-Liste — "Übersetzen"-Button

[`SourcesPanel.tsx`](frontend/src/app/workspace/[uuid]/_components/sources/SourcesPanel.tsx):

Pro Source-Row, sichtbar wenn:
- Source-Typ ist Audio/Video (hat DE-VTT)
- Workspace-Mode ist `manual`
- User ist Owner
- Kein EN-VTT vorhanden (Server-Status)

Action: POST `/api/ai-assistant/sources/{uuid}/translate-en` — UI zeigt Spinner, danach grünes Badge "EN ✓".

Bei `mode=auto`: Button nicht sichtbar, läuft im Hintergrund nach Ingest.
Bei `mode=off`: Button nicht sichtbar.

### Page-Wiring

[`page.tsx`](frontend/src/app/workspace/[uuid]/page.tsx) — neuer State nur für Translation-Mode:

```ts
const [translationMode, setTranslationMode] = useState<"off"|"auto"|"manual">("manual");

const onChangeTranslationMode = (m) => {
  setTranslationMode(m);
  fetch(`/api/ai-assistant/workspaces/${uuid}`, {
    method:"PATCH", body: JSON.stringify({ transcript_translation_mode: m })
  });
};
```

`onSettingsLoaded` in [`useWorkspaceInit.ts`](frontend/src/app/workspace/[uuid]/_hooks/useWorkspaceInit.ts) liest zusätzlich `transcript_translation_mode` aus Workspace-Detail-Response.

**Hilde:** [`SettingsMenu.tsx`](frontend/src/app/workspace/[uuid]/_components/layout/SettingsMenu.tsx) ruft `useHildePref()` selbst auf — kein Prop-Drilling, kein Page-State. [`ChatPanel.tsx`](frontend/src/app/workspace/[uuid]/_components/chat/ChatPanel.tsx) und übrige Hilde-Stellen nutzen den Hook unverändert weiter. `useHildePref.ts` bleibt bestehen.

---

## Migration / Daten-Pfad

Reihenfolge:

1. **DB-Migration** (idempotent): nur neue Spalte `aia_workspaces.transcript_translation_mode`
2. **Backend-Endpoints**: Workspace-Detail liefert `transcript_translation_mode`, PATCH akzeptiert den Key, Owner-Check
3. **Ingest-Logik** mit Mode-Check ausrollen
4. **Frontend**:
   - `HeaderSettings.tsx` löschen
   - `HeaderLanguageSwitch` + `HeaderThemeToggle` als Platzhalter ergänzen (Header.tsx + HeaderMobileMenu.tsx)
   - `SettingsMenu.tsx` umbauen: Sprache-Feld raus, Hilde-Toggle (via `useHildePref()`) rein, Translation-Mode-Block (Owner-only) rein
5. **Manuelle-Translation-Endpoint** + Source-Liste-Button

`chat_lang` und `useHildePref` bleiben in dieser Iteration komplett unverändert.

---

## Component-Übersicht (final)

```
frontend/src/components/layout/
  Header.tsx                     # ohne HeaderSettings, dafür Lang+Theme als Platzhalter
  HeaderLanguageSwitch.tsx       # NEU (Platzhalter: lokaler State, keine Persistenz)
  HeaderThemeToggle.tsx          # NEU (Platzhalter: lokaler State, keine Persistenz)
  HeaderMobileMenu.tsx           # ergänzt um Lang+Theme (Platzhalter)
  HeaderSettings.tsx             # GELÖSCHT

frontend/src/hooks/
  useHildePref.ts                # bestehend, unverändert (global per localStorage)

frontend/src/app/workspace/[uuid]/_components/layout/
  SettingsMenu.tsx               # umgebaut: + Hilde-Toggle (useHildePref), + Translation-Mode (Owner), − chatLang-Feld
  WorkspaceTopbar.tsx            # Props-Anpassung (chatLang weg, isOwner + translationMode rein)

backend/src/features/ai_assistant/
  routes/sources/translate.py    # NEU: POST /sources/{uuid}/translate-en
  routes/workspaces.py           # PATCH akzeptiert transcript_translation_mode
  tasks/ingestion.py             # mode-Check vor Auto-Dispatch
  schemas.py                     # Workspace-Schema +transcript_translation_mode
backend/src/core/db/schema.py    # Migration: +Spalte transcript_translation_mode
```

---

## Open Items (verschoben)

Folgende Ideen wurden besprochen, sind aber **nicht** Teil dieser Spec:

- Job-fertig-Sound (Header)
- Reduced-Motion-Toggle (Hilde-/Mascot-Animationen)
- Schriftgröße / A11y-Skalierung
- Default-Quellen-Auswahl beim Workspace-Open
- Citations-Stil (inline / Fußnoten)
- Per-User-TTS-Stimme (sobald ElevenLabs-Per-User aktiv)
- Funktionale Dark-Mode-CSS-Variablen (Theme-Toggle persistiert nur, CSS folgt)
- Co-Dozenten-Konzept (würde `isOwner` von `isLecturer && user_id-match` entkoppeln)

---

## Risiken / Edge Cases

- **Header-Items als Platzhalter**: User klickt auf Sprache/Theme und erwartet Wirkung. Mitigation:
  - Sprache-Switch: nach Klick auf `EN` keine Wirkung sichtbar. Optional Tooltip "Bald verfügbar" oder Disabled-Hover-State auf den Optionen. Empfehlung: das Element wirkt aktiv, aber wir nehmen den Look-only-Charakter als bewusste UX-Risiko-Inkaufnahme im Konzept.
  - Theme-Toggle: Icon wechselt sichtbar (Sun↔Moon), aber sonst nichts — gleicher Hinweis-Text empfohlen, oder Toggle subtil mit niedrigerer Opacity bis CSS folgt.
- **Translation-Mode-Wechsel auf bestehenden Quellen**: Mode wirkt nur auf **neue** Quellen ab Wechsel-Zeitpunkt. Schon übersetzte EN-VTTs bleiben (auch bei `mode=off`). Manuelle Re-Translation: nicht in dieser Spec.
- **Source-Liste-Button bei `mode=auto`**: nicht sichtbar — wenn ein Auto-Lauf failt (DeepL-Quote alle), gibt es keinen User-Recovery-Pfad. Lecturer müsste auf `manual` schalten und neu triggern. Akzeptabel; Quote-Failure-Notification ist eigenes Item (Memory: "Nie spammen, Retry-Button").
- **Bestehender `chat_lang`-Pfad**: bleibt aktiv. Sobald der Header-Switch echt wird, müssen `aia_user_settings.chat_lang` und Lese-Pfade in einem Folge-PR abgebaut werden — bis dahin ist die Wirkung des Header-Switches null.

---

## Acceptance Criteria

- [ ] `HeaderSettings.tsx` ist gelöscht, kein Modal mehr im Header
- [ ] Header zeigt `HeaderLanguageSwitch` (Default DE) und `HeaderThemeToggle` (Default Sun) **als Platzhalter** — zwischen Jobs und Admin (am alten Einstellungen-Slot)
- [ ] Sprache-Switch zeigt Dropdown DE/EN, Klick auf EN ändert nur den Trigger-Text (kein localStorage, keine Propagation)
- [ ] Theme-Toggle wechselt Icon Sun↔Moon (kein localStorage, kein `data-theme`)
- [ ] AIA-`SettingsMenu` zeigt Hilde-Toggle (global per `useHildePref`), Translation-Mode-Block (nur Owner)
- [ ] Hilde-Wert bleibt in `localStorage["ki-assistent-hilde-enabled"]`, `useHildePref.ts` ist unverändert
- [ ] DB-Migration: nur neue Spalte `transcript_translation_mode` (idempotent)
- [ ] Workspace-Detail-Endpoint liefert `transcript_translation_mode`
- [ ] PATCH-Workspace mit `transcript_translation_mode` funktioniert nur als Owner (403 sonst)
- [ ] Ingest dispatcht EN-Translation **nur bei** `mode=auto`
- [ ] Quellen-Liste hat Übersetzen-Button bei `mode=manual` (Owner-only, nur Audio/Video ohne EN-VTT)
- [ ] Mobile-Menü zeigt Sprache + Theme als Platzhalter
- [ ] Keine deutschen Identifier neu eingeführt (Memory-Rule)
- [ ] Phosphor-Icons im Header sind `weight="bold"` outline-only (Memory-Rule)
