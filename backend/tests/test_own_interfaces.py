"""Own interfaces: the permission, the one-time disclaimer, and that nobody else speaks with a person's key."""

import base64
import json
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROUTE = "src.routes.own_interfaces"
_REAL_CLIENT = httpx.Client


def _own(pid=41, owner=7, protocol="elevenlabs", voices=None):
    return {"id": pid, "name": f"x{pid}", "protocol": protocol, "base_url": "https://api.elevenlabs.io",
            "api_key": "sk_live_abcdef", "enabled": True, "capabilities": ["tts"], "concurrency": {"tts": 2},
            "voices": voices if voices is not None else [{"voice_id": "v1", "name": "Anna", "language": ""}],
            "owner_user_id": owner, "created_at": "2026-09-30T10:00:00"}


def _shared(pid=3):
    return {"id": pid, "name": "myLab", "protocol": "openai_compat", "base_url": "http://mylab",
            "api_key": None, "enabled": True, "capabilities": ["tts"], "voices": [], "owner_user_id": None}


def _mock_http(monkeypatch, handler):
    """Every httpx.Client of the test answers through the handler instead of the network."""
    monkeypatch.setattr(httpx, "Client", lambda **kw: _REAL_CLIENT(
        transport=httpx.MockTransport(handler), **{k: v for k, v in kw.items() if k != "transport"}))


@pytest.fixture
def client_as():
    from src.app import app
    from src.dependencies import get_current_user, get_settings
    from src.dependencies_rbac import get_user_permissions
    from src.permissions import permissions_for_system_role
    from src.security.auth import verify_auth

    def make(role="staff", user_id=7):
        get_settings.cache_clear()
        app.dependency_overrides[verify_auth] = lambda: None
        app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id, "role": role}
        # The tool gate reads the person itself, not through the overridable dependency.
        app.dependency_overrides[get_user_permissions] = lambda: permissions_for_system_role(role)
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


# ── The permission ────────────────────────────────────────────────────────────

def test_teachers_and_admins_have_it_students_do_not():
    from src.permissions import permissions_for_system_role
    from src.permissions_registry import PERM_GENERAL_INTERFACES

    assert permissions_for_system_role("staff").has(PERM_GENERAL_INTERFACES)
    assert permissions_for_system_role("admin").has(PERM_GENERAL_INTERFACES)
    assert not permissions_for_system_role("user").has(PERM_GENERAL_INTERFACES)


def test_the_permission_opens_no_settings_area():
    """A settings key would make every teacher look like a partial admin."""
    from src.permissions import permissions_for_system_role

    assert permissions_for_system_role("staff").allow_admin_panel is False


def test_a_student_gets_no_page(client_as):
    assert client_as(role="user").get("/me/interfaces").status_code == 403


# ── The disclaimer comes first ────────────────────────────────────────────────

def test_without_consent_the_page_shows_nothing_but_the_notice(client_as):
    with patch(f"{ROUTE}.db.get_interfaces_consent",
               return_value={"interfaces_consent_at": None, "interfaces_consent_version": None}), \
         patch("src.services.own_tts.access.db.get_interfaces_consent",
               return_value={"interfaces_consent_version": None}), \
         patch(f"{ROUTE}.db.list_own_providers") as rows:
        body = client_as().get("/me/interfaces").json()

    assert body["consent"]["accepted"] is False
    assert body["interfaces"] == []
    assert {v["key"] for v in body["vendors"]} >= {"elevenlabs", "gemini", "fish"}
    rows.assert_not_called()


def test_connecting_before_the_consent_is_refused(client_as):
    with patch("src.services.own_tts.access.db.get_interfaces_consent",
               return_value={"interfaces_consent_version": None}), \
         patch(f"{ROUTE}.db.create_provider") as create:
        response = client_as().post("/me/interfaces", json={"vendor": "elevenlabs", "api_key": "sk_12345678"})

    assert response.status_code == 403
    create.assert_not_called()


def test_the_consent_is_stored_with_its_version(client_as):
    from src.services.own_tts.access import CONSENT_VERSION

    with patch(f"{ROUTE}.db.set_interfaces_consent") as write:
        assert client_as().post("/me/interfaces/consent").status_code == 200
    write.assert_called_once_with(7, CONSENT_VERSION)


def test_an_older_consent_counts_as_none():
    from src.services.own_tts import access

    with patch.object(access.db, "get_interfaces_consent",
                      return_value={"interfaces_consent_version": access.CONSENT_VERSION - 1}):
        assert access.has_consent(7) is False


# ── Connecting ────────────────────────────────────────────────────────────────

@pytest.fixture
def consented():
    with patch("src.services.own_tts.access.db.get_interfaces_consent",
               return_value={"interfaces_consent_version": 99}), \
         patch(f"{ROUTE}.export_crypto.is_export_key_configured", return_value=True):
        yield


def test_connect_checks_the_key_and_stores_an_own_row(client_as, consented):
    voices = [{"voice_id": "v1", "name": "Anna", "language": "", "description": ""}]
    with patch("src.services.own_tts.elevenlabs.list_voices", return_value=voices) as ask, \
         patch(f"{ROUTE}.db.list_own_providers", return_value=[]), \
         patch(f"{ROUTE}.db.create_provider", return_value=_own()) as create:
        response = client_as().post("/me/interfaces", json={"vendor": "elevenlabs", "api_key": " sk_live_abcdef "})

    assert response.status_code == 200
    ask.assert_called_once_with("sk_live_abcdef")
    kw = create.call_args.kwargs
    assert kw["owner_user_id"] == 7
    assert kw["protocol"] == "elevenlabs"
    assert kw["base_url"] == "https://api.elevenlabs.io"
    assert kw["capabilities"] == ["tts"]
    assert kw["api_key"] == "sk_live_abcdef"
    # The page only ever sees the end of the key.
    assert response.json()["interface"]["key_last_chars"] == "cdef"
    assert "api_key" not in response.json()["interface"]


def test_a_second_key_for_the_same_service_replaces_the_first(client_as, consented):
    with patch("src.services.own_tts.elevenlabs.list_voices", return_value=[{"voice_id": "v2", "name": "B"}]), \
         patch(f"{ROUTE}.db.list_own_providers", return_value=[_own()]), \
         patch(f"{ROUTE}.db.update_provider", return_value=_own()) as update, \
         patch(f"{ROUTE}.db.create_provider") as create:
        client_as().post("/me/interfaces", json={"vendor": "elevenlabs", "api_key": "sk_other_key"})

    create.assert_not_called()
    assert update.call_args.args == (41,)
    assert update.call_args.kwargs["api_key"] == "sk_other_key"


def test_a_rejected_key_says_so_in_words(client_as, consented):
    from src.services.own_tts._base import KEY_INVALID, OwnInterfaceError

    with patch("src.services.own_tts.elevenlabs.list_voices",
               side_effect=OwnInterfaceError(KEY_INVALID, "ElevenLabs", "401")), \
         patch(f"{ROUTE}.db.create_provider") as create:
        response = client_as().post("/me/interfaces", json={"vendor": "elevenlabs", "api_key": "sk_wrong_key"},
                                    headers={"Accept-Language": "de"})

    assert response.status_code == 400
    assert "ElevenLabs hat den Schlüssel abgelehnt" in response.json()["detail"]
    create.assert_not_called()


def test_an_unknown_service_is_refused(client_as, consented):
    response = client_as().post("/me/interfaces", json={"vendor": "intranet", "api_key": "sk_12345678"})
    assert response.status_code == 400


def test_without_the_server_secret_no_key_is_taken(client_as):
    """The notice promises an encrypted key."""
    with patch("src.services.own_tts.access.db.get_interfaces_consent",
               return_value={"interfaces_consent_version": 99}), \
         patch(f"{ROUTE}.export_crypto.is_export_key_configured", return_value=False), \
         patch(f"{ROUTE}.db.create_provider") as create:
        response = client_as().post("/me/interfaces", json={"vendor": "elevenlabs", "api_key": "sk_12345678"})

    assert response.status_code == 503
    create.assert_not_called()


def test_nobody_removes_someone_elses_interface(client_as, consented):
    with patch(f"{ROUTE}.db.get_provider", return_value=_own(owner=8)), \
         patch(f"{ROUTE}.db.delete_provider") as delete:
        assert client_as().delete("/me/interfaces/41").status_code == 404
    delete.assert_not_called()


def test_the_admin_area_does_not_know_own_interfaces():
    from src.routes.admin import providers as admin

    with patch.object(admin.db, "get_provider", return_value=_own()):
        assert admin._shared_provider(41) is None
    with patch.object(admin.db, "get_provider", return_value=_shared()):
        assert admin._shared_provider(3)["id"] == 3


# ── Nobody else speaks with a person's key ───────────────────────────────────

def test_route_check_refuses_a_foreign_interface():
    from src.services.own_tts import access

    with patch.object(access.db, "get_provider", return_value=_own(owner=8)), \
         patch.object(access, "has_consent", return_value=True):
        with pytest.raises(HTTPException) as e:
            access.check_voice_provider(41, {"user_id": 7, "role": "staff"}, "de")
    assert e.value.status_code == 404


def test_route_check_refuses_the_owner_without_permission():
    from src.services.own_tts import access

    with patch.object(access.db, "get_provider", return_value=_own(owner=7)), \
         patch.object(access, "has_consent", return_value=True):
        with pytest.raises(HTTPException):
            access.check_voice_provider(41, {"user_id": 7, "role": "user"}, "de")
        access.check_voice_provider(41, {"user_id": 7, "role": "staff"}, "de")


def test_route_check_lets_shared_providers_through():
    from src.services.own_tts import access

    with patch.object(access.db, "get_provider", return_value=_shared()):
        access.check_voice_provider(3, {"user_id": 7, "role": "user"}, "de")


def test_the_client_is_only_built_for_the_owners_jobs(monkeypatch):
    from src import dependencies
    from src.services.own_tts import elevenlabs

    monkeypatch.setattr(dependencies.db, "get_provider", lambda pid: _own(owner=7))
    assert dependencies.get_tts_client_for_provider(41) is None
    assert dependencies.get_tts_client_for_provider(41, 8) is None
    assert isinstance(dependencies.get_tts_client_for_provider(41, 7), elevenlabs.Client)


def test_own_interfaces_never_hand_over_to_the_admins_fallback(monkeypatch):
    from src.services import tts_job_provider

    monkeypatch.setattr(tts_job_provider.db, "get_provider", lambda pid: _own())
    monkeypatch.setattr(tts_job_provider, "_there", lambda p: False)
    monkeypatch.setattr(tts_job_provider, "_usable_fallback", lambda pid: pytest.fail("no fallback"))
    wahl = tts_job_provider.pick(41, ["v1"])
    assert (wahl.provider_id, wahl.voices, wahl.fallback) == (41, ("v1",), False)


def test_the_voice_list_shows_own_voices_but_never_preselects_them(client_as, monkeypatch):
    from src import dependencies

    async def reachable(user):
        assert user["user_id"] == 7
        return [_shared(3) | {"voices": [{"voice_id": "alloy", "name": "Alloy", "language": "de"}]}, _own()]

    monkeypatch.setattr(dependencies, "get_reachable_tts_providers_with_voices", reachable)
    with patch("src.services.tts_standard.star_id", return_value=None), \
         patch("src.services.tts_standard.default_voice_setting", return_value=None), \
         patch("src.dependencies_rbac.is_released_now", return_value=True):
        response = client_as().get("/tts/providers-with-voices", headers={"Accept-Language": "de"})

    assert response.status_code == 200, response.text
    body = response.json()
    own = [p for p in body["providers"] if p["own"]]
    assert [p["name"] for p in own] == ["ElevenLabs (eigener Zugang)"]
    assert body["default"] == {"provider_id": 3, "voice_id": "alloy"}


# ── The outside services ─────────────────────────────────────────────────────

def test_elevenlabs_speaks_with_the_key_header_and_sends_no_speed():
    from src.services.own_tts import elevenlabs

    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers["xi-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=b"ID3mp3")

    client = elevenlabs.Client("sk_abc", elevenlabs.MODEL)
    with _REAL_CLIENT(transport=httpx.MockTransport(handler)) as http:
        audio = client._one(http, "Hallo\nWelt 3", "voice9", 2.0, "de")

    assert audio == b"ID3mp3"
    assert seen["url"].startswith("https://api.elevenlabs.io/v1/text-to-speech/voice9")
    assert "output_format=mp3_44100_128" in seen["url"]
    assert seen["key"] == "sk_abc"
    assert seen["body"]["model_id"] == "eleven_multilingual_v2"
    assert "voice_settings" not in seen["body"]
    assert seen["body"]["text"] == "Hallo Welt 3"


@pytest.mark.parametrize("status,body,code", [
    (401, {"detail": {"status": "invalid_api_key", "message": "Invalid API key"}}, "keyInvalid"),
    (401, {"detail": {"status": "quota_exceeded", "message": "insufficient quota"}}, "quota"),
    (400, {"detail": {"status": "quota_exceeded"}}, "quota"),
    (429, {"detail": {"status": "too_many_concurrent_requests"}}, "unreachable"),
])
def test_elevenlabs_refusals_are_told_apart(status, body, code):
    from src.services.own_tts import elevenlabs
    from src.services.own_tts._base import OwnInterfaceError

    client = elevenlabs.Client("sk_abc", elevenlabs.MODEL)
    with _REAL_CLIENT(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))) as http:
        with pytest.raises(OwnInterfaceError) as e:
            client._one(http, "Hallo", "voice9", 1.0, "de")
    assert e.value.code == code


def test_elevenlabs_reads_every_page_of_voices(monkeypatch):
    from src.services.own_tts import elevenlabs

    def handler(request):
        if "next_page_token" in str(request.url):
            return httpx.Response(200, json={"voices": [{"voice_id": "b", "name": "B"}], "has_more": False})
        return httpx.Response(200, json={"voices": [{"voice_id": "a", "name": "A", "labels": {"gender": "female"}}],
                                         "has_more": True, "next_page_token": "t2"})

    _mock_http(monkeypatch, handler)
    voices = elevenlabs.list_voices("sk_abc")
    assert [v["voice_id"] for v in voices] == ["a", "b"]
    assert voices[0]["language"] == "" and voices[0]["description"] == "female"


def test_elevenlabs_balance_comes_from_the_subscription(monkeypatch):
    from src.services.own_tts import elevenlabs

    _mock_http(monkeypatch, lambda r: httpx.Response(200, json={
        "character_count": 1200, "character_limit": 10000, "next_character_count_reset_unix": 1790000000}))
    assert elevenlabs.credit("sk_abc")["used"] == 1200
    _mock_http(monkeypatch, lambda r: httpx.Response(401, json={"detail": {"status": "missing_permissions"}}))
    assert elevenlabs.credit("sk_abc") is None


def test_gemini_turns_the_wav_into_mp3(monkeypatch):
    from src.services.own_tts import gemini

    wav = b"RIFF" + b"\0" * 40 + b"\1\0" * 10
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(wav).decode()}}]}}]})

    monkeypatch.setattr(gemini, "to_mp3", lambda audio, rate, speed=1.0: b"MP3:" + audio[:4] + f"{speed}".encode())
    client = gemini.Client("AIza", gemini.MODEL)
    with _REAL_CLIENT(transport=httpx.MockTransport(handler)) as http:
        audio = client._one(http, "Hallo", "Kore", 0.8, "de")

    # The tempo of the call is not applied, the voice keeps its own.
    assert audio == b"MP3:RIFF1.0"
    assert seen["url"].endswith(f"/v1beta/models/{gemini.MODEL}:generateContent")
    voice = seen["body"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"]
    assert voice == "Kore"


@pytest.mark.parametrize("status,body,code", [
    (400, {"error": {"status": "INVALID_ARGUMENT", "message": "API key not valid. Please pass a valid API key.",
                     "details": [{"reason": "API_KEY_INVALID"}]}}, "keyInvalid"),
    (400, {"error": {"status": "FAILED_PRECONDITION", "message": "User location is not supported"}},
     "billingRequired"),
    (429, {"error": {"status": "RESOURCE_EXHAUSTED",
                     "details": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}}, "quota"),
    (429, {"error": {"status": "RESOURCE_EXHAUSTED",
                     "details": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]}},
     "unreachable"),
])
def test_gemini_refusals_are_told_apart(monkeypatch, status, body, code):
    from src.services.own_tts import gemini
    from src.services.own_tts._base import OwnInterfaceError

    _mock_http(monkeypatch, lambda r: httpx.Response(status, json=body))
    with pytest.raises(OwnInterfaceError) as e:
        gemini.list_voices("AIza")
    assert e.value.code == code


def test_gemini_offers_its_fixed_voices_after_a_good_key(monkeypatch):
    from src.services.own_tts import gemini

    _mock_http(monkeypatch, lambda r: httpx.Response(200, json={"name": f"models/{gemini.MODEL}"}))
    names = [v["voice_id"] for v in gemini.list_voices("AIza")]
    assert len(names) == 30 and "Kore" in names


def test_fish_lists_own_voices_first_and_each_voice_once(monkeypatch):
    from src.services.own_tts import fish_audio

    def handler(request):
        url = str(request.url)
        if "api-credit" in url:
            return httpx.Response(200, json={"credit": "0"})
        if "self=true" in url:
            return httpx.Response(200, json={"items": [{"_id": "mine", "title": "Meine Stimme"}]})
        return httpx.Response(200, json={"items": [{"_id": "mine", "title": "dup"},
                                                   {"_id": "pub", "title": "Sprecher", "languages": ["de"]}]})

    _mock_http(monkeypatch, handler)
    voices = fish_audio.list_voices("fk")
    assert [v["voice_id"] for v in voices] == ["mine", "pub"]
    assert voices[0]["name"] == "Meine Stimme"


def test_fish_empty_balance_is_a_quota_refusal():
    from src.services.own_tts import fish_audio
    from src.services.own_tts._base import OwnInterfaceError

    client = fish_audio.Client("fk", fish_audio.MODEL)
    handler = lambda r: httpx.Response(402, json={"status": 402, "message": "Insufficient credits"})  # noqa: E731
    with _REAL_CLIENT(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(OwnInterfaceError) as e:
            client._one(http, "Hallo", "pub", 1.0, "de")
    assert e.value.code == "quota" and e.value.permanent


def test_raw_audio_and_wav_both_become_mp3():
    """Runs ffmpeg for real, a broken argument would only show up in a job otherwise."""
    import shutil

    from src.services.own_tts._base import to_mp3

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg fehlt")
    pcm = b"\0\0" * 24000
    assert len(to_mp3(pcm, 24000)) > 1000
    assert len(to_mp3(pcm, 24000, speed=1.3)) > 500


def test_a_failed_job_tells_the_persons_own_reason():
    from src.services.own_tts._base import QUOTA, OwnInterfaceError
    from src.tasks import _errors

    with patch.object(_errors, "job_locale", return_value="de"), \
         patch.object(_errors.db, "update_job_status") as status:
        _errors.handle_task_exception("j" * 32, OwnInterfaceError(QUOTA, "ElevenLabs"), task_label="TTS")

    assert status.call_args.args[1] == "failed"
    assert "Guthaben bei ElevenLabs" in status.call_args.kwargs["error_message"]
