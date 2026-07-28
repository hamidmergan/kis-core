"""Die Route screencast_translate gibt es nicht mehr.

Sie stand im Admin als eigene Zeile, wirkte aber nie: der Screencast liest sein
Übersetzungsmodell aus doc_translate. Wer dort etwas einstellte, wunderte sich,
warum nichts passiert. Beide Werkzeuge übersetzen dieselben Dateiformate,
deshalb gibt es jetzt genau eine Einstellung.

Achtung beim Lesen: "screencast_translate" existiert weiter als Name eines
Auftragstyps in der Job-Tabelle. Das ist etwas anderes als eine Route und muss
bleiben.
"""

from src.features.ai_providers.repository.feature_routes import (
    FEATURES,
    USER_CHOICE_FEATURES,
)
from src.services.feature_route_check import _CHAT_LIKE_FEATURES


def test_route_is_gone():
    assert "screencast_translate" not in FEATURES
    assert "screencast_translate" not in USER_CHOICE_FEATURES
    assert "screencast_translate" not in _CHAT_LIKE_FEATURES


def test_doc_translate_still_exists_and_stays_user_choice():
    """Sie ist der Ersatz. Fällt sie weg, kann niemand mehr übersetzen."""
    assert "doc_translate" in FEATURES
    assert "doc_translate" in USER_CHOICE_FEATURES


def test_job_tool_name_is_untouched():
    """Der Auftragstyp heißt weiter so, sonst verschwinden alte Aufträge
    aus dem Verlauf."""
    from src.routes.admin._registries import TOOL_LABELS

    assert "screencast_translate" in TOOL_LABELS
