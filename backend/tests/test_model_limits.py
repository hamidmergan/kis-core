"""Checks the one-off model measurement and the budgets computed from it."""
import pytest

from src.services import model_limits as ml


# ── Read the window size from the refusal ───────────────────────────────────

_ECHTE_ABSAGEN = [
    # Answer to the probe (max_tokens deliberately impossibly large)
    ("max_tokens=99999999 cannot be greater than max_model_len=max_total_tokens=262144. "
     "Please request fewer output tokens. (parameter=max_tokens, value=99999999)", 262144),
    ("max_tokens=99999999 cannot be greater than max_model_len=max_total_tokens=20080.", 20080),
    # Answer to a real, oversized request
    ("This model's maximum context length is 65536 tokens. However, your request has "
     "73251 input tokens. Please reduce the length of the input messages.", 65536),
    # OpenAI-Wortlaut
    ("This model's maximum context length is 8192 tokens, however you requested 9000 tokens.", 8192),
]


@pytest.mark.parametrize("text,erwartet", _ECHTE_ABSAGEN)
def test_liest_fenstergroesse_aus_echten_absagen(text, erwartet):
    assert ml.parse_window(text) == erwartet


def test_absage_ohne_zahl_ergibt_nichts():
    assert ml.parse_window("Unauthorized") is None
    assert ml.parse_window("") is None
    assert ml.parse_window(None) is None


def test_nimmt_die_kleinere_zahl_wenn_beide_vorkommen():
    """With two numbers in the refusal the window is the smaller one."""
    text = ("This model's maximum context length is 65536 tokens. However, your request "
            "has 73251 input tokens.")
    assert ml.parse_window(text) == 65536


# ── Token in Zeichen ────────────────────────────────────────────────────────

def test_budget_bleibt_unter_dem_fenster():
    """Computed for the densest case so everything fits."""
    zeichen = ml.context_chars(262144, ml.CHAT_SHARE)
    assert zeichen / 3.0 <= 262144 * ml.CHAT_SHARE + 1


def test_kleines_fenster_ergibt_kleines_budget():
    """A small window would have split every request under the old fixed budget."""
    assert ml.context_chars(20080, ml.CHAT_SHARE) < 60000


def test_grosses_fenster_ergibt_grosses_budget():
    assert ml.context_chars(262144, ml.CHAT_SHARE) > 250000


def test_werkzeuge_bekommen_mehr_als_der_chat():
    """A tool may take more of the window than the chat."""
    assert ml.context_chars(262144, ml.TOOL_SHARE) > ml.context_chars(262144, ml.CHAT_SHARE)


def test_budget_faellt_nie_unter_den_boden():
    """Even a tiny window must not yield a budget of 0."""
    assert ml.context_chars(10, ml.CHAT_SHARE) >= ml.MIN_CONTEXT_CHARS


# ── Denken abschalten ───────────────────────────────────────────────────────

class _Nachricht:
    def __init__(self, content, reasoning=""):
        self.content = content
        self.reasoning = reasoning


class _Wahl:
    def __init__(self, nachricht):
        self.message = nachricht
        self.finish_reason = "stop"


class _Antwort:
    def __init__(self, content, reasoning=""):
        self.choices = [_Wahl(_Nachricht(content, reasoning))]


class _Denker:
    """A model that thinks and whose thinking exactly one switch turns off."""

    def __init__(self, wirksam="chat_template_kwargs", window=262144, lehnt_ab=()):
        self.wirksam = wirksam
        self.window = window
        self.lehnt_ab = set(lehnt_ab)
        self.aufrufe = []

    def create(self, **kwargs):
        self.aufrufe.append(kwargs)
        if kwargs.get("max_tokens", 0) > 1_000_000:
            raise RuntimeError(
                f"max_tokens={kwargs['max_tokens']} cannot be greater than "
                f"max_model_len=max_total_tokens={self.window}."
            )
        for name in self.lehnt_ab:
            if _schalter_gesetzt(kwargs, name):
                raise RuntimeError(f"Unrecognized request argument supplied: {name}")
        if _schalter_gesetzt(kwargs, self.wirksam):
            return _Antwort("ok")
        return _Antwort("ok", reasoning="Ich denke kurz nach, " * 40)


def _schalter_gesetzt(kwargs, name) -> bool:
    koerper = dict(kwargs.get("extra_body") or {})
    koerper.update({k: v for k, v in kwargs.items() if k != "extra_body"})
    if name == "chat_template_kwargs":
        return bool((koerper.get("chat_template_kwargs") or {}).get("enable_thinking") is False)
    if name == "reasoning_effort_none":
        return koerper.get("reasoning_effort") == "none"
    return False


def _messen(client):
    return ml.measure_with(lambda **kw: client.create(**kw))


def test_misst_fenster_denken_und_wirksamen_schalter():
    client = _Denker(wirksam="chat_template_kwargs", window=262144)
    profil = _messen(client)
    assert profil.window_tokens == 262144
    assert profil.source == ml.QUELLE_GEMESSEN
    assert profil.thinks is True
    assert profil.think_off == "chat_template_kwargs"


def test_findet_den_zweiten_schalter_wenn_der_erste_nichts_bewirkt():
    """Recognised by the effect, not by the error."""
    client = _Denker(wirksam="reasoning_effort_none")
    profil = _messen(client)
    assert profil.think_off == "reasoning_effort_none"


def test_ueberspringt_einen_schalter_den_der_anbieter_ablehnt():
    """Beide Schalter blind mitzuschicken zerlegt strenge Anbieter."""
    assert ml._SWITCH_ORDER[0] == "chat_template_kwargs"
    client = _Denker(wirksam="reasoning_effort_none", lehnt_ab=("chat_template_kwargs",))
    profil = _messen(client)
    assert profil.think_off == "reasoning_effort_none"


def test_modell_ohne_denken_wird_nicht_weiter_behelligt():
    class _Stiller(_Denker):
        def create(self, **kwargs):
            self.aufrufe.append(kwargs)
            if kwargs.get("max_tokens", 0) > 1_000_000:
                raise RuntimeError("max_model_len=max_total_tokens=131072.")
            return _Antwort("ok")

    client = _Stiller()
    profil = _messen(client)
    assert profil.thinks is False
    assert profil.think_off == ""
    # Probe plus one trial question, no switch rounds
    assert len(client.aufrufe) == 2


def test_schweigsamer_anbieter_bleibt_unbekannt():
    """For a silent model no number is invented."""
    class _Schweiger(_Denker):
        def create(self, **kwargs):
            if kwargs.get("max_tokens", 0) > 1_000_000:
                return _Antwort("ok")
            return _Antwort("ok")

    profil = _messen(_Schweiger())
    assert profil.window_tokens == 0
    assert profil.source == ml.QUELLE_UNBEKANNT
    assert not profil.measured


def test_unbekanntes_fenster_deckelt_nichts(monkeypatch):
    """Without knowledge about the model only the admin setting applies."""
    profil = ml.ModelProfile(0, ml.QUELLE_UNBEKANNT, False, "")
    monkeypatch.setattr(ml, "profile_for_feature", lambda feature="chat": profil)
    assert ml.cap_for_model(250000, ml.CHAT_SHARE) == 250000
    assert ml.as_dict(profil)["context_chars"] is None


# ── Extra arguments for the real call ───────────────────────────────────────

def test_baut_die_zusatzangabe_zum_gemerkten_schalter():
    profil = ml.ModelProfile(window_tokens=1, source=ml.QUELLE_GEMESSEN,
                             thinks=True, think_off="chat_template_kwargs")
    assert ml.think_off_body(profil) == {"chat_template_kwargs": {"enable_thinking": False}}

    profil2 = ml.ModelProfile(window_tokens=1, source=ml.QUELLE_GEMESSEN,
                              thinks=True, think_off="reasoning_effort_none")
    assert ml.think_off_body(profil2) == {"reasoning_effort": "none"}


def test_kein_denker_bekommt_keine_zusatzangabe():
    profil = ml.ModelProfile(window_tokens=1, source=ml.QUELLE_GEMESSEN,
                             thinks=False, think_off="")
    assert ml.think_off_body(profil) == {}


# ── Shortening after a refusal ──────────────────────────────────────────────

def _nachrichten(system_chars, kontext_chars, frage_chars=50):
    return [
        {"role": "system", "content": "S" * system_chars},
        {"role": "user", "content": "K" * kontext_chars},
        {"role": "user", "content": "F" * frage_chars},
    ]


def test_kuerzen_bringt_die_nachrichten_unter_das_budget():
    gekuerzt = ml.fit_messages(_nachrichten(1000, 100000), 20000)
    assert sum(len(m["content"]) for m in gekuerzt) <= 20000


def test_kuerzen_nimmt_der_groessten_nachricht_die_mitte():
    """The middle is cut, system instruction and question stay untouched."""
    gekuerzt = ml.fit_messages(_nachrichten(1000, 100000), 20000)
    assert gekuerzt[0]["content"] == "S" * 1000
    assert gekuerzt[2]["content"] == "F" * 50
    mitte = gekuerzt[1]["content"]
    assert mitte.startswith("K")
    assert mitte.endswith("K")
    assert len(mitte) < 100000


def test_kuerzen_laesst_passende_nachrichten_in_ruhe():
    original = _nachrichten(100, 500)
    assert ml.fit_messages(original, 20000) == original


def test_kuerzen_gibt_niemals_leere_nachrichten_zurueck():
    """A tiny budget must not boil the context down to nothing."""
    gekuerzt = ml.fit_messages(_nachrichten(1000, 100000), 10)
    assert all(m["content"] for m in gekuerzt)


def test_kuerzen_ruehrt_das_original_nicht_an():
    original = _nachrichten(1000, 100000)
    ml.fit_messages(original, 20000)
    assert len(original[1]["content"]) == 100000


def test_denker_ohne_wirksamen_schalter_bekommt_auch_keine():
    """Thinking that cannot be turned off gets nothing ineffective sent along."""
    profil = ml.ModelProfile(window_tokens=1, source=ml.QUELLE_GEMESSEN,
                             thinks=True, think_off="")
    assert ml.think_off_body(profil) == {}
