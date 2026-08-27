"""Builds Markdown from the fields of the model answer while it is still streaming."""

from typing import Optional

from loguru import logger

from src.features.ai_assistant.prompts.refusal_prompts import is_bare_term

# A backslash before a letter is almost always LaTeX here and stays.
_ECHTE_FLUCHT = {"n": "\n", '"': '"', "\\": "\\", "/": "/"}

# Only '\u' carries four hex digits behind it and therefore means a real character.
_HEX = "0123456789abcdefABCDEF"

# Without a cap the model keeps filling the field until the real material runs out.
MAX_EINTRAEGE = 5

# Between two fields the model has hung in whitespace for minutes.
LEERLAUF_MAX = 200


class AntwortStrom:
    """Takes the model's chunks and hands out finished text for the chat."""

    def __init__(self, max_eintraege: int | None = MAX_EINTRAEGE) -> None:
        self.gap: Optional[str] = None
        self._luecke = ""
        self._zustand = "start"
        self._gesehen = ""
        self._puffer = ""
        self._wort = ""
        self._offen = False
        self._escape = False
        self._hex: Optional[str] = None
        self._hoch = ""
        self._erstes_item = True
        self._eintraege = 0
        self._max = max_eintraege
        self.genug = False
        # When this is True there is nothing left to get from this stream.
        self.fertig = False
        self.grund = ""
        self._leerlauf = 0

    def feed(self, stueck: str) -> str:
        """Returns whatever part of this chunk belongs in the chat."""
        if self._zustand == "roh":
            return stueck
        return "".join(self._zeichen(z) for z in stueck)

    # -- Hilfen ---------------------------------------------------------------

    def _entwerte(self, z: str) -> str:
        """Resolves a JSON escape and leaves LaTeX commands intact."""
        if self._hex is None:
            self._escape = False
            if z == "u":
                self._hex = ""
                return ""
            return _ECHTE_FLUCHT.get(z, "\\" + z)
        if z not in _HEX:
            # Not four hex digits, so it was a LaTeX command after all.
            ziffern, self._hex = self._hex, None
            return "\\u" + ziffern + z
        self._hex += z
        if len(self._hex) < 4:
            return ""
        ziffern, self._hex = self._hex, None
        return self._aus_hex(ziffern)

    def _aus_hex(self, ziffern: str) -> str:
        """Assembles a character from four hex digits, from two halves if needed."""
        punkt = int(ziffern, 16)
        if 0xD800 <= punkt <= 0xDBFF:
            self._hoch = ziffern
            return ""
        hoch, self._hoch = self._hoch, ""
        if hoch and 0xDC00 <= punkt <= 0xDFFF:
            paar = chr(int(hoch, 16)) + chr(punkt)
            return paar.encode("utf-16", "surrogatepass").decode("utf-16")
        return chr(punkt)

    def _sammle(self, z: str) -> Optional[str]:
        """Reads a string and returns it as soon as it ends."""
        if not self._offen:
            if z == '"':
                self._offen = True
                self._wort = ""
            return None
        if self._escape or self._hex is not None:
            self._wort += self._entwerte(z)
        elif z == "\\":
            self._escape = True
        elif z == '"':
            self._offen = False
            return self._wort
        else:
            self._wort += z
        return None

    def _schluss_melden(self, grund: str) -> None:
        """Remembers why it stops here so the caller can end the stream."""
        if not self.fertig:
            self.fertig = True
            self.grund = grund

    def _leerlauf_pruefen(self, z: str) -> None:
        """Counts whitespace between the fields and reports a stuck model."""
        if self._offen or not z.isspace():
            self._leerlauf = 0
            return
        self._leerlauf += 1
        if self._leerlauf > LEERLAUF_MAX:
            logger.warning("leerlauf: modell schreibt nur noch leerraum in zustand {}",
                           self._zustand)
            self._schluss_melden("leerlauf")

    def _zeige(self, text: str) -> str:
        """Holds back whatever goes beyond the ceiling on entries."""
        if self._max is None or self._eintraege <= self._max:
            return text
        self.genug = True
        return ""

    def _absage(self, bruecke: str = "") -> str:
        """Joins refusal and bridge part into a single sentence."""
        luecke, self._luecke = self._luecke, ""
        if not luecke:
            return (self._schluss(self._gross(bruecke), ":") + "\n") if bruecke else ""
        # Only report, do not repair: the code can only build a sentence in German.
        if is_bare_term(luecke):
            logger.warning("absage: begriff statt satz im feld, {!r}", luecke)
        # gap carries the rendered form, otherwise chat.py no longer finds the refusal line.
        if not bruecke:
            self.gap = self._schluss(self._gross(luecke), ".")
            return self.gap + "\n\n"
        # The join adds the comma, one of its own at the sentence end would be the second.
        self.gap = self._gross(luecke.rstrip().rstrip(".,"))
        return self._schluss(self.gap + ", " + bruecke.lstrip(" ,"), ":") + "\n"

    @staticmethod
    def _gross(satz: str) -> str:
        """Capitalise the start, the bridge's lowercase rule bleeds onto the refusal."""
        return satz[:1].upper() + satz[1:]

    @staticmethod
    def _schluss(satz: str, zeichen: str) -> str:
        """Adds the missing sentence end, the model often drops it while streaming."""
        kern = satz.rstrip()
        return kern if not kern or kern[-1] in ".:!?" else kern + zeichen

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
        self._leerlauf_pruefen(z)

        if zustand == "start":
            self._gesehen += z
            if not self._gesehen.strip():
                return ""
            # Not JSON: the schema was ignored, everything falls through unchanged.
            if not self._gesehen.lstrip().startswith("{"):
                self._zustand = "roh"
                return self._gesehen
            if '"no_info_sentence"' in self._gesehen:
                self._zustand = "absage"
            return ""

        if zustand == "absage":
            if not self._offen and z in "nul":
                self._puffer += z
                if self._puffer.endswith("null"):
                    self._puffer = ""
                    self._zustand = "warte_bridge"
                return ""
            fertig = self._sammle(z)
            if fertig is not None:
                self.gap = fertig
                # Hold back until the bridge arrives, the two form one sentence.
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
                self._eintraege += 1
                return self._zeige(f"- **{begriff}**: ")
            return ""

        if zustand == "text":
            if not self._offen:
                if z == '"':
                    self._offen = True
                    self._wort = ""
                return ""
            if self._escape or self._hex is not None:
                return self._zeige(self._entwerte(z))
            if z == "\\":
                self._escape = True
                return ""
            if z == '"':
                self._offen = False
                self._zustand = "warte_term"
                self._puffer = ""
                return self._zeige("\n")
            return self._zeige(z)

        if zustand == "warte_body":
            if self._warte_auf(z, '"body"'):
                self._zustand = "body"
            return ""

        if zustand == "body":
            if not self._offen:
                if z == '"':
                    self._offen = True
                return ""
            if self._escape or self._hex is not None:
                return self._entwerte(z)
            if z == "\\":
                self._escape = True
                return ""
            if z == '"':
                self._zustand = "fertig"
                self._schluss_melden("schema")
                return ""
            return z

        return ""
