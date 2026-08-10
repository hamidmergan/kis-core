"""Der einmalige Schritt, der den Quiz-Vorrat leert.

Zwei Dinge können hier richtig teuer schiefgehen, und beide prüft dieser Test.

Erstens: eine Aufgabe aus dem Vorrat wird nicht in den Satz kopiert, der Satz zeigt nur
dorthin, und die Inhaltsspalten seiner Zeile sind leer. Ein blankes DELETE setzt den
Verweis per ON DELETE SET NULL auf NULL und macht damit jeden fertigen Satz leer, der auf
eine dieser Zeilen zeigt. Zurückgeschrieben werden muss also VOR dem Löschen.

Zweitens: anders als beim abgeschafften Hörverstehen entstehen beim Quiz laufend neue
Vorratszeilen. Ohne Schlüssel in settings würfe der Schritt den Vorrat bei jedem Neustart
des Backends wieder weg.
"""

from src.core.db import schema


class _FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)
        self.calls = []

    def execute(self, sql, params=None):
        # Ungekuerzt: der Test prueft Bestandteile der Anweisung, ein Abschneiden wuerde
        # ihn stillschweigend gruen machen.
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None


def test_erst_zurueckschreiben_dann_loeschen():
    cur = _FakeCursor([None])
    assert schema._reset_quiz_pool_once(cur) is True
    anweisungen = [sql for sql, _ in cur.calls]
    update = next(i for i, s in enumerate(anweisungen)
                  if s.startswith("UPDATE aia_exercise_items"))
    delete = next(i for i, s in enumerate(anweisungen)
                  if s.startswith("DELETE FROM aia_exercise_pool"))
    assert update < delete
    assert "p.tool = 'quiz'" in anweisungen[update]
    assert "tool = 'quiz'" in anweisungen[delete]
    # Der Verweis der Satzzeile bekommt jedes Inhaltsfeld zurueck, sonst steht die
    # Aufgabe hinterher ohne Optionen da.
    for feld in ("back", "options", "correct_idx", "sources", "extras"):
        assert f"{feld} = p.{feld}" in anweisungen[update]


def test_der_schluessel_wird_danach_gesetzt():
    cur = _FakeCursor([None])
    schema._reset_quiz_pool_once(cur)
    letzte_sql, letzte_params = cur.calls[-1]
    assert letzte_sql.startswith("INSERT INTO settings")
    assert letzte_params == (schema._QUIZ_POOL_RESET_KEY,)


def test_mit_gesetztem_schluessel_passiert_nichts():
    """Sonst waere jeder Backend-Neustart ein Verlust des ganzen Quiz-Vorrats."""
    cur = _FakeCursor([("true",)])
    assert schema._reset_quiz_pool_once(cur) is False
    anweisungen = [sql for sql, _ in cur.calls]
    assert not any(s.startswith("DELETE") or s.startswith("UPDATE") for s in anweisungen)
