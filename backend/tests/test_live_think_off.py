"""The live chat client turns thinking off from the stored measurement, nothing else."""

from src.services import feature_router, model_limits


def _binding(feature="chat"):
    return feature_router.FeatureBinding(
        feature=feature, model="gemma4:26b-mlx",
        provider={"id": 25, "name": "Ollama (local)", "base_url": "http://ollama:11434/v1",
                  "api_key": None})


class _Client:
    _extra_body = None


def _gemessen(monkeypatch, profil):
    monkeypatch.setattr(model_limits, "stored_profile", lambda pid, model: profil)


def test_denkendes_modell_bekommt_den_gespeicherten_schalter(monkeypatch):
    _gemessen(monkeypatch, model_limits.ModelProfile(32768, model_limits.QUELLE_GESETZT,
                                                     True, "reasoning_effort_none"))
    c = _Client()
    feature_router.attach_stored_think_off(c, _binding())
    assert c._extra_body == {"reasoning_effort": "none"}
    assert c._model_profile.think_off == "reasoning_effort_none"


def test_das_fenster_lernen_bleibt_aus(monkeypatch):
    """Without a provider id the chat never stores a window learned from a refusal."""
    _gemessen(monkeypatch, model_limits.ModelProfile(32768, model_limits.QUELLE_GESETZT,
                                                     True, "reasoning_effort_none"))
    c = _Client()
    feature_router.attach_stored_think_off(c, _binding())
    assert not hasattr(c, "_provider_id")


def test_nicht_denkendes_modell_bleibt_unveraendert(monkeypatch):
    _gemessen(monkeypatch, model_limits.ModelProfile(32768, model_limits.QUELLE_GEMESSEN,
                                                     False, ""))
    c = _Client()
    feature_router.attach_stored_think_off(c, _binding())
    assert c._extra_body is None


def test_ohne_messung_wird_nichts_angehaengt(monkeypatch):
    _gemessen(monkeypatch, None)
    c = _Client()
    feature_router.attach_stored_think_off(c, _binding())
    assert c._extra_body is None
    assert not hasattr(c, "_model_profile")


def test_nur_chat_aehnliche_funktionen(monkeypatch):
    _gemessen(monkeypatch, model_limits.ModelProfile(32768, model_limits.QUELLE_GESETZT,
                                                     True, "reasoning_effort_none"))
    c = _Client()
    feature_router.attach_stored_think_off(c, _binding("embedding"))
    assert c._extra_body is None


# ── The tools: their retrying client sends the switch on every call ──────────

class _Fake:
    def __init__(self):
        self.calls = []
        outer = self

        class _C:
            def create(self, **kw):
                outer.calls.append(kw)
                return "ok"

        class _Ch:
            completions = _C()

        self.chat = _Ch()


def test_werkzeug_client_schickt_den_schalter_bei_jedem_aufruf():
    from src.features.ai_assistant.tasks._retry import RetryingClient
    fake = _Fake()
    c = RetryingClient(fake, extra_body={"reasoning_effort": "none"})
    c.chat.completions.create(model="m", messages=[])
    assert fake.calls[0]["extra_body"] == {"reasoning_effort": "none"}


def test_eigene_extra_body_eines_aufrufs_geht_vor():
    from src.features.ai_assistant.tasks._retry import RetryingClient
    fake = _Fake()
    c = RetryingClient(fake, extra_body={"reasoning_effort": "none", "a": 1})
    c.chat.completions.create(model="m", messages=[], extra_body={"a": 2})
    assert fake.calls[0]["extra_body"] == {"reasoning_effort": "none", "a": 2}


def test_ohne_schalter_bleibt_der_aufruf_unveraendert():
    from src.features.ai_assistant.tasks._retry import RetryingClient
    fake = _Fake()
    RetryingClient(fake).chat.completions.create(model="m", messages=[])
    assert "extra_body" not in fake.calls[0]
