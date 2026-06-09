# STT Provider-Dropdown (Sprache in Text)

Datum: 2026-06-09

## Ziel
Im globalen Tool "Sprache in Text" (STT) soll der Nutzer einen Provider auswaehlen
koennen. Auswahl umfasst nur die im Admin fuer STT freigegebenen Provider und davon
nur die aktuell erreichbaren. Muster wie beim bestehenden TTS-Tool.

## Entscheidungen
- Admin-Modell: STT wird user_choice-Feature (Multi-Pill mit Modell pro Provider), wie TTS.
- Erreichbarkeit: Live-Probe beim Laden der Tool-Seite (parallel, kurzer Timeout),
  ueber die bestehende Adapter-probe (GET /health bzw. /v1/models). Kein neuer Hintergrundjob.

## Aenderungen

### Backend
1. `feature_routes.py`: `stt` zu `USER_CHOICE_FEATURES` hinzufuegen.
2. `dependencies.resolve_whisper_client(provider_id: int | None = None)`:
   aufloesen ueber `feature_router.resolve("stt", user_provider_id=provider_id)`.
   Ohne provider_id wie bisher (Default-Route).
3. Neuer Endpoint `GET /transcription/providers`:
   - liest `feature_router.providers_for_feature("stt")` (freigegebene, aktivierte).
   - probed jeden Provider parallel (asyncio.to_thread, kurzer Timeout).
   - gibt nur erreichbare zurueck: `{ providers: [{id, name}], default_id }`.
4. `POST /transcription`: optionales Form-Feld `provider_id`.
   Validierung gegen user_choices (sonst 400), an Task weiterreichen.
5. `run_transcribe(..., provider_id=None)`: an `resolve_whisper_client` weitergeben.

### Frontend
6. Admin `FeatureRoutingCard.tsx`: `stt` in `SPLIT_USER_CHOICE_FEATURES` und in die
   Multi-Pill-mit-Modell-pro-Provider-Darstellung (Branch fuer tts/doc_translate).
7. Tool `tools/stt/page.tsx`: Provider beim Laden holen, `Select`-Dropdown nur bei >1,
   `provider_id` im FormData mitsenden. Exakt das TTS-Muster.

### i18n
8. `tools.stt.providerLabel` und `tools.stt.noProvider` (de/en).

## Rueckwaertskompatibel
Hat der Admin keine STT-Provider freigegeben, liefert der Endpoint leer, kein Dropdown,
Transcribe laeuft wie heute ueber die Default-Route ohne provider_id.

## Tests
- `resolve_whisper_client` mit/ohne provider_id (gueltig, ungueltig -> FeatureNotConfigured).
- Provider-Endpoint filtert nicht erreichbare heraus.
