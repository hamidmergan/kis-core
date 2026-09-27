"""KIS wartet auf die Text-KI so lange, wie myLab einen Aufruf selbst laufen lässt.

Lasttest mit großen Dateien am 26.09.: Die Dienste sind auf Aufrufe bis etwa 300 s ausgelegt,
KIS brach aber nach 120 s ab. Eine Gliederung über 200 Seiten konnte so nie gelingen.
"""

from src.services.openai_compat_llm.base import _LLM_HTTP_TIMEOUT


def test_ein_planungsaufruf_darf_so_lange_dauern_wie_myLab_ihn_laufen_laesst():
    assert _LLM_HTTP_TIMEOUT.read >= 300
