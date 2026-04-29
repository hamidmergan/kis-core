# Storage Refactor — Design Spec

**Date:** 2026-04-29
**Branch:** `refactor/storage`
**Scope:** Approach B (Best Practice), Bestand wegwerfbar (Bucket wird gewipet)

---

## Goals

1. Stabile, GDPR-freundliche Object Keys (kein PII im Pfad)
2. Pfad pure aus immutablen IDs (`user_id` + `job_uuid`/`module_uuid`) → keine DB-Roundtrips für Pfad-Lookup
3. Konsistentes Layout über alle Features (`users/{user_id}/{feature}/...`, `tmp/`)
4. Performance: Batch-Delete + parallele Writes
5. Naming-Konsistenz: `aia/` statt `kia/` (DB ist schon migriert)
6. Lifecycle: tmp-Ordner serverseitig per MinIO-Policy verfallen lassen
7. Dead Code raus (`save_file`, 11 ungenutzte Imports, `username`-Spalte aus `jobs`)

## Non-Goals

- Server-Side-Encryption (KMS-Setup im MinIO-Stack overkill für Single-Tenant)
- Multi-Tenant-Prefix (kein Bedarf laut Plan: nur THL)
- Soft-Delete + Background-GC (Hard-Delete reicht, kein Compliance-Bedarf)
- User-UUID-Migration (User-Tabelle bleibt SERIAL; `user_id` als opaker Identifier reicht)

---

## Neues Object-Key-Layout

```
users/{user_id}/jobs/{job_uuid}/input.{ext}
users/{user_id}/jobs/{job_uuid}/output.{ext}
users/{user_id}/jobs/{job_uuid}/result.json
users/{user_id}/jobs/{job_uuid}/meta.json
users/{user_id}/jobs/{job_uuid}/audio/slide_NNN.mp3              # finale Pre-Computed-TTS
users/{user_id}/jobs/{job_uuid}/render_cache/slide_NNN.mp3       # Crash-Recovery (war: tts_audio/)
users/{user_id}/jobs/{job_uuid}/render_cache/slide_NNN_align.json

users/{user_id}/aia/modules/{module_uuid}/sources/{source_uuid}.{ext}
users/{user_id}/aia/modules/{module_uuid}/sources/{source_uuid}.md
users/{user_id}/aia/modules/{module_uuid}/sources/{source_uuid}_transcript.txt
users/{user_id}/aia/modules/{module_uuid}/sources/{source_uuid}_transcript.{lang}.vtt
users/{user_id}/aia/modules/{module_uuid}/outputs/{filename}

tmp/pptx/{file_id}.pptx                                          # Lifecycle: 24h TTL
```

**Rationale:**
- `users/{user_id}/…` als Top-Level → GDPR-Bulk-Delete = ein Prefix-List+Delete
- `user_id` (SERIAL) statt `username` → stabil, kein PII in Logs, refactor-resistent
- Kein `created_at`/`tool` mehr im Pfad → DB ist Source of Truth, Pfad ist opak
- `kia/` → `aia/` → Konsistenz mit DB-Tabellen (`aia_modules`, `aia_sources`)
- `tts_audio/` → `render_cache/` → klarere Semantik (Crash-Recovery, nicht "TTS-Audio")
- `tmp/` flach unter Bucket-Root → MinIO-Lifecycle-Policy einfach zuordenbar

---

## DB-Änderungen

### `jobs`-Tabelle
- **DROP:** `username TEXT` — denormalisierte Kopie, ungenutzt für UI/Stats (die JOINen schon auf `users.ldap_username` in `_queries.py:174` und `_stats.py`); wird heute nur in `_crud.py:25` beim Insert befüllt und in `storage.py:173` für Pfad gelesen — beide Stellen entfallen mit dem Refactor
- **Keine neue Spalte:** Pfad wird pure aus `user_id` + `job_uuid` abgeleitet. Beide sind immutable.

### `aia_*`-Tabellen
- **Keine Änderung am Schema.** `aia_sources.file_path` bleibt (zeigt auf Hauptdatei mit neuem Layout). Modul-Outputs werden weiter on-the-fly konstruiert via pure Funktion.

### Migration (idempotent in `init_db()`)
```python
ALTER TABLE jobs DROP COLUMN IF EXISTS username;
```

**Bestand:** Bucket wird gewipet, alle Job-Rows + AIA-Sources werden vorher per `TRUNCATE jobs, aia_sources, aia_modules CASCADE` gelöscht (CASCADE räumt FK-abhängige Tabellen mit). Manuell durch User auszuführen vor erstem Start mit neuem Code.

---

## Code-Änderungen

### `backend/src/storage.py`

**Streichen:**
- `save_file(user_id, …)` (Dead Code, keine Caller)
- `_job_folder_name(job_uuid)` (DB-Roundtrip-Quelle)
- `_PPTX_TMP_PREFIX` Konstante (durch Modul-Konstante `TMP_PPTX_PREFIX = "tmp/pptx"` ersetzen)

**Neu (pure Funktionen, kein DB-Call):**
- `job_prefix(user_id: int, job_uuid: str) -> str` → `f"users/{user_id}/jobs/{job_uuid}"`
- `aia_module_prefix(user_id: int, module_uuid: str) -> str` → `f"users/{user_id}/aia/modules/{module_uuid}"`
- `aia_source_key(user_id: int, module_uuid: str, source_uuid: str, ext: str) -> str` → analog
- `delete_prefix(prefix: str) -> None` — Batch via `delete_objects` (max 1000/Call)
- `init_lifecycle_policy()` — setzt 24h-TTL für `tmp/` Prefix, im `init_storage()` aufgerufen, mit ClientError-Catch falls Berechtigung fehlt

**Refactor:**
- Alle bisherigen `_job_key(job_uuid, …)` Calls bekommen `user_id` als Parameter und nutzen `job_prefix()`. Caller haben `user_id` typischerweise im `Job`-Objekt aus DB; wo nicht, einmaliger Lookup `SELECT user_id FROM jobs WHERE job_uuid = %s` (single column, schnell, optional cachebar).
- `save_audio_cache` parallelisieren (ThreadPoolExecutor analog `get_all_audio_slides`)
- `delete_job_folder(user_id, job_uuid)` → `delete_prefix(job_prefix(user_id, job_uuid))` (Batch)
- `clear_tts_audio_cache` → `clear_render_cache(user_id, job_uuid)` → `delete_prefix(f"{job_prefix(...)}/render_cache/")` (Batch)
- `tts_audio/` (Pfad-String) → `render_cache/` in `services/screencast/generation.py`

**Signatur-Änderungen (Breaking, aber lokal):**
- `save_queue_file`, `save_job_file`, `get_job_file`, `save_result_file`, `save_result_json`, `save_result_meta`, `load_result_meta`, `delete_job_folder`, `clear_render_cache`, `save_audio_cache`, `get_audio_slide`, `get_audio_slide_count`, `get_all_audio_slides`, `job_file_exists` → bekommen `user_id: int` als ersten Parameter zusätzlich zu `job_uuid`.
- Alle Caller (Routes/Tasks) haben `user_id` aus dem Job-Record, das Reichen-Durch ist mechanisch.

### Aufrufer-Anpassungen

- `backend/src/routes/screencast/render.py` — `clear_render_cache(job)` statt `clear_tts_audio_cache(uuid)`
- `backend/src/tasks/screencast_tasks/_render.py` — analog
- `backend/src/services/screencast/generation.py` — `tts_audio/` → `render_cache/` in Pfaden
- `backend/src/features/ai_assistant/routes/_helpers.py` — `kia/{username}/…` → `users/{user_id}/aia/…`
- `backend/src/features/ai_assistant/tasks/_helpers.py` — analog
- 11 Files: ungenutzten `save_file`-Import entfernen

### Lifecycle Policy (MinIO)

Im `init_storage()` einmalig setzen:
```python
_s3().put_bucket_lifecycle_configuration(
    Bucket=_S3_BUCKET,
    LifecycleConfiguration={
        "Rules": [{
            "ID": "tmp-pptx-24h",
            "Filter": {"Prefix": "tmp/pptx/"},
            "Expiration": {"Days": 1},
            "Status": "Enabled",
        }]
    }
)
```

---

## Performance-Erwartungen

| Operation | Vorher | Nachher |
|---|---|---|
| Pfad-Lookup pro S3-Call | 1 DB-Roundtrip | 0 (Pfad in Memory) |
| `delete_job_folder` (100 Slides) | 1+100 Roundtrips | 1+1 Roundtrip (Batch) |
| `save_audio_cache` (100 Slides) | 100 sequentielle PUTs | ~10 parallele PUTs |
| `pptx_tmp` Cleanup | Sync-Code, Race-Risk | Server-seitig 24h |

---

## Risiken / offene Punkte

- **`init_lifecycle_policy()` Berechtigung:** MinIO-Service-User braucht `s3:PutLifecycleConfiguration` — falls fehlt, Catch + Log-Warning, kein Hard-Fail.
- **Reihenfolge Insert ↔ Storage-Write:** `INSERT INTO jobs` muss vor erstem `put_object` passieren, damit `user_id` in DB ist (aktuell teilweise schon so, im Plan verifizieren).
- **`stream_s3_object` für AIA-Sources:** nutzt heute `source["file_path"]` direkt — bleibt unverändert, da `file_path` nach Refactor ebenfalls den vollen Key enthält.

## Test-Strategie

- Unit: `build_job_prefix`, `build_aia_module_prefix` — pure Funktionen, einfache Asserts
- Integration: gegen lokales MinIO, mit Bucket-Wipe als Setup. Tests:
  - Save → Get → Delete-Roundtrip für Job + AIA-Module
  - Batch-Delete: 1500 Objects in einem Prefix → max 2 `delete_objects`-Calls
  - Lifecycle-Policy: nach `init_storage()` ist Rule aktiv
- Manuell: Screencast-Tool E2E (Translate → Render → Audio-Playback) auf neuem Branch
