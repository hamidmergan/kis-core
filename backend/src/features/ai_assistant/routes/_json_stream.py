"""Baut aus den Feldern der Modellantwort schon waehrend des Streamens Markdown."""

from typing import Optional

_ENTWERTET = {"n": "\n", "t": "\t", "r": "\r", "b": "", "f": ""}


class AntwortStrom:
    """Nimmt die Haeppchen des Modells und gibt fertigen Text fuer den Chat heraus."""

    def __init__(self) -> None:
        self.gap: Optional[str] = None
        self._luecke = ""
        self._zustand = "start"
        self._gesehen = ""
        self._puffer = ""
        self._wort = ""
        self._offen = False
        self._escape = False
        self._erstes_item = True

    def feed(self, stueck: str) -> str:
        """Gibt zurueck, was von diesem Haeppchen in den Chat gehoert."""
        if self._zustand == "roh":
            return stueck
        return "".join(self._zeichen(z) for z in stueck)

    # -- Hilfen ---------------------------------------------------------------

    def _sammle(self, z: str) -> Optional[str]:
        """Liest eine Zeichenkette ein und gibt sie zurueck, sobald sie zu Ende ist."""
        if not self._offen:
            if z == '"':
                self._offen = True
                self._wort = ""
            return None
        if self._escape:
            self._wort += _ENTWERTET.get(z, z)
            self._escape = False
        elif z == "\\":
            self._escape = True
        elif z == '"':
            self._offen = False
            return self._wort
        else:
            self._wort += z
        return None

    def _absage(self, bruecke: str = "") -> str:
        """Fuegt Absage und Brueckenteil zu einem einzigen Satz zusammen."""
        luecke, self._luecke = self._luecke, ""
        if not luecke:
            return (self._gross(bruecke) + "\n") if bruecke else ""
        # gap traegt die gerenderte Form, sonst findet chat.py die Absage-Zeile nicht mehr.
        if not bruecke:
            self.gap = self._gross(luecke)
            return self.gap + "\n\n"
        self.gap = self._gross(luecke.rstrip().rstrip("."))
        return self.gap + ", " + bruecke + "\n"

    @staticmethod
    def _gross(satz: str) -> str:
        """Satzanfang gross, weil die Kleinschreib-Regel der Bruecke auf die Absage abfaerbt."""
        return satz[:1].upper() + satz[1:]

    def _warte_auf(self, z: str, schluessel: str) -> bool:
        self._puffer += z
        if schluessel in self._puffer:
            self._puffer = ""
            return True
        return False

    # -- Zustaende ------------------------------------------------------------

    def _zeichen(self, z: str) -> str:
        zustand = self._zustand
        if zustand == "roh":
            return z

        if zustand == "start":
            self._gesehen += z
            if not self._gesehen.strip():
                return ""
            # Kein JSON: das Schema wurde ignoriert, alles faellt unveraendert durch.
            if not self._gesehen.lstrip().startswith("{"):
                self._zustand = "roh"
                return self._gesehen
            if '"gap"' in self._gesehen:
                self._zustand = "gap"
            return ""

        if zustand == "gap":
            if not self._offen and z in "nul":
                self._puffer += z
                if self._puffer.endswith("null"):
                    self._puffer = ""
                    self._zustand = "warte_bridge"
                return ""
            fertig = self._sammle(z)
            if fertig is not None:
                self.gap = fertig
                # Zurueckhalten, bis die Bruecke da ist: beide bilden einen Satz.
                self._luecke = fertig
                self._zustand = "warte_bridge"
            return ""

        if zustand == "warte_bridge":
            if self._warte_auf(z, '"bridge"'):
                self._zustand = "bridge"
            elif '"body"' in self._puffer:
                self._puffer = ""
                self._zustand = "body"
                return self._absage()
            return ""

        if zustand == "bridge":
            if not self._offen and z in "nul":
                self._puffer += z
                if self._puffer.endswith("null"):
                    self._puffer = ""
                    self._zustand = "warte_items"
                    return self._absage()
                return ""
            fertig = self._sammle(z)
            if fertig is not None:
                self._zustand = "warte_items"
                return self._absage(fertig)
            return ""

        if zustand == "warte_items":
            if self._warte_auf(z, '"items"'):
                self._zustand = "warte_term"
            elif '"body"' in self._puffer:
                self._puffer = ""
                self._zustand = "body"
                return self._absage()
            return ""

        if zustand == "warte_term":
            if z == "]":
                self._zustand = "warte_body"
                self._puffer = ""
                return ""
            if self._warte_auf(z, '"term"'):
                self._zustand = "term"
            return ""

        if zustand == "term":
            fertig = self._sammle(z)
            if fertig is not None:
                self._puffer = fertig
                self._zustand = "warte_text"
            return ""

        if zustand == "warte_text":
            self._gesehen += z
            if '"text"' in self._gesehen:
                self._gesehen = ""
                begriff, self._puffer = self._puffer, ""
                self._zustand = "text"
                return f"- **{begriff}**: "
            return ""

        if zustand == "text":
            if not self._offen:
                if z == '"':
                    self._offen = True
                    self._wort = ""
                return ""
            if self._escape:
                self._escape = False
                return _ENTWERTET.get(z, z)
            if z == "\\":
                self._escape = True
                return ""
            if z == '"':
                self._offen = False
                self._zustand = "warte_term"
                self._puffer = ""
                return "\n"
            return z

        if zustand == "warte_body":
            if self._warte_auf(z, '"body"'):
                self._zustand = "body"
            return ""

        if zustand == "body":
            if not self._offen:
                if z == '"':
                    self._offen = True
                return ""
            if self._escape:
                self._escape = False
                return _ENTWERTET.get(z, z)
            if z == "\\":
                self._escape = True
                return ""
            if z == '"':
                self._zustand = "fertig"
                return ""
            return z

        return ""
