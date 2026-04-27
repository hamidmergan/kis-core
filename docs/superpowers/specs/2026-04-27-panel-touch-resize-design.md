# Panel-Resize auf Touch-Geräten (iPad)

**Datum:** 2026-04-27
**Branch:** feat/global-schedule (oder neuer Branch)
**Status:** Spec ready for review

## Problem

Das 3-Panel-Layout (`Quellen | Chat | Studio`) im Workspace läuft auf iPad bewusst im Desktop-Modus (siehe Kommentar in [usePanelLayout.ts:14](frontend/src/app/workspaces/[uuid]/_hooks/usePanelLayout.ts#L14)). Der Divider-Drag zwischen den Panels ist jedoch nur an `mousedown`/`mousemove`/`mouseup` gebunden ([usePanelLayout.ts:123](frontend/src/app/workspaces/[uuid]/_hooks/usePanelLayout.ts#L123)) und funktioniert deshalb auf iPad (Touch + Pencil) nicht zuverlässig. User können Panels auf iPad weder breiter noch schmaler ziehen, was speziell im Landscape-Modus stört, weil dort genug Platz für sinnvolle Anpassungen wäre.

Zusätzlich ist der Drag-Handle nur 8px breit und nur on-hover sichtbar — ohne Hover-State auf Touch-Geräten ist er für User unauffindbar.

## Ziel

- Panel-Resize per Touch (Finger + Apple Pencil) auf iPad ermöglichen.
- Drag-Handle auf Touch-Geräten dauerhaft sichtbar und ausreichend groß für Finger-Bedienung.
- Desktop-Verhalten (Maus, hover-only Handle) unverändert lassen.

## Out of Scope

- Keine Grip-Dots, Icons oder sonstige visuelle Indikatoren am Handle (visuelles Rauschen, keep it simple).
- Keine separate Persistierung der Panel-Breiten pro Device-Typ — eine `localStorage`-Größe für alle.
- Kein Doppeltap-Reset, Snap-to-Grid o.ä.
- Smartphone-Layout (Single-Panel + Tabs) bleibt unverändert — nicht betroffen, weil der Drag dort gar nicht existiert.

## Architektur

### Datei 1: `frontend/src/app/workspaces/[uuid]/_hooks/usePanelLayout.ts`

`startDrag` umstellen von `MouseEvent` auf `PointerEvent`:

- Signatur: `(divider: 1 | 2, e: React.PointerEvent) => void`
- Im Body:
  - `e.preventDefault()` bleibt (verhindert Text-Selection auf Maus, Scroll/Zoom auf Touch).
  - `(e.target as HTMLElement).setPointerCapture(e.pointerId)` — fängt alle weiteren Pointer-Events bis Release ab, auch wenn der Cursor das Handle verlässt.
  - Listener: `pointermove` und `pointerup` statt `mousemove`/`mouseup`.
  - `pointermove`-Handler liest `ev.clientX` (gleich wie bei MouseEvent — keine Änderung der Berechnung).
  - `pointerup`-Handler entfernt beide Listener und persistiert Breiten.
- `clampDelta` und Refs-Logik bleiben **unverändert** (rein x-basiert).

### Datei 2: `frontend/src/app/workspaces/[uuid]/_components/layout/WorkspacePanelsLayout.tsx`

`DragHandle`-Komponente und Aufrufer anpassen:

- `DragHandle`-Props: `onMouseDown` → `onPointerDown` (Typ: `(e: React.PointerEvent) => void`).
- Aufrufer-Sites (Zeilen 86, 96): `onMouseDown={...}` → `onPointerDown={...}`.
- Handle-Element bekommt inline-Style `touchAction: "none"` — verhindert iOS-Scroll/Zoom während Drag.
- Inline-Style `width` und `height` werden entfernt, stattdessen CSS-Klassen `panel-drag-handle` (Container) und `panel-drag-handle-bar` (innerer Strich) vergeben. Default-Werte (8px / 48px / hover-only opacity) leben dann in `globals.css`, coarse-pointer Override ebenfalls dort.

### Datei 3: `frontend/src/app/globals.css`

Neue Regeln (Tailwind kann `pointer: coarse` nicht out-of-the-box, deshalb nativ in CSS):

```css
.panel-drag-handle {
  width: 8px;
}
.panel-drag-handle-bar {
  width: 2px;
  height: 48px;
  border-radius: 9999px;
  background-color: var(--kb);
  opacity: 0;
  transition: opacity 150ms;
}
.panel-drag-handle:hover .panel-drag-handle-bar {
  opacity: 1;
}

@media (pointer: coarse) {
  .panel-drag-handle {
    width: 14px;
  }
  .panel-drag-handle-bar {
    opacity: 1;
    height: 64px;
  }
}
```

Damit fällt das `group/group-hover`-Tailwind-Konstrukt im JSX weg und das Verhalten ist an einer Stelle gebündelt.

## Daten-Flow

Unverändert. Pointer-Events liefern dieselben `clientX`-Werte wie Mouse-Events. Persistenz (`setP1Width`/`setP2Width`/`setP3Width` als React-State) bleibt 1:1.

## Edge-Cases

- **Pencil:** `pointerType === "pen"` läuft automatisch durch denselben Codepfad — keine Sonderbehandlung.
- **Maus auf Desktop:** PointerEvents sind ein Superset von MouseEvents. Funktioniert identisch, hover-only Handle bleibt durch fehlende `(pointer: coarse)`-Match erhalten.
- **Mehrere Finger:** `setPointerCapture` bindet an genau eine `pointerId`. Zweiter Finger triggert keinen zweiten Drag.
- **Pointer wird abrupt unterbrochen** (z.B. iOS-Notch-Swipe): `pointercancel` wird nicht explizit behandelt — der laufende Drag bleibt dann offen. **Mitigation:** zusätzlich `pointercancel`-Listener registrieren, der wie `pointerup` aufräumt (ohne State-Update, damit die Position auf Stand des letzten `pointermove` einrastet).

## Test-Plan

Manuell, weil reine UI-Interaktion:

- [ ] **Desktop Maus** (Chrome/Firefox): Drag funktioniert wie vorher, Handle ist im Idle unsichtbar, erscheint on-hover.
- [ ] **iPad Safari Portrait:** Handle dauerhaft sichtbar (14px breit, 64px hoher Strich). Finger-Drag verschiebt Divider, andere Panel passt sich an.
- [ ] **iPad Safari Landscape:** Wie Portrait. Insbesondere Drag von links nach rechts und zurück über die volle Breite.
- [ ] **iPad Apple Pencil:** Drag funktioniert wie mit Finger.
- [ ] **iPad Safari, Drag-Geste verlässt das Fenster** (an den Rand): Drag wird sauber beendet, kein hängender State.
- [ ] **Smartphone Portrait + Landscape:** Layout zeigt weiter Single-Panel + Tab-Switcher, kein Drag-Handle sichtbar (nicht betroffen).
- [ ] **Container-Restart nicht nötig** — reines Frontend (npm run dev reload genügt).

## Risiken

- **Niedrig:** Logik-Änderung minimal, Berechnung identisch.
- **Mittel:** `touch-action: none` auf dem Handle sollte Scroll-Konflikte vermeiden, muss aber auf iPad Safari verifiziert werden — falls dort Probleme auftreten, ggf. `touch-action: pan-y` als Fallback.

## Aufwand

Klein: ~30–60 Min Implementierung + manuelles Testen auf iPad.
