"""Baut aus den Feldern der Modellantwort schon waehrend des Streamens Markdown."""

from typing import Optional

from loguru import logger

from src.features.ai_assistant.prompts.refusal_prompts import is_bare_term

# Ein Rueckstrich vor einem Buchstaben ist in dieser Antwort fast immer ein LaTeX-Befehl
# und kein JSON-Zeichen, darum bleibt er stehen.
_ECHTE_FLUCHT = {"n": "\n", '"': '"', "\\": "\\", "/": "/"}

# Nur "\\u" traegt vier Hex-Ziffern hinter sich und meint darum ein echtes Zeichen.
_HEX = "0123456789abcdefABCDEF"

# Ohne Deckel fuellt das Modell das Feld weiter, bis der echte Stoff alle ist.
MAX_EINTRAEGE = 5

# Zwischen zwei Feldern erlaubt JSON beliebig viel Leerraum, und genau darin blieb das
# Modell schon minutenlang haengen. Ein huebsch eingerueckter Aufbau bleibt weit darunter.
LEERLAUF_MAX = 200


class AntwortStrom:
    """Nimmt die Haeppchen des Modells und gibt fertigen Text fuer den Chat heraus."""

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
        # Steht das auf True, ist aus diesem Strom nichts mehr zu holen.
        self.fertig = False
        self.grund = ""
        self._leerlauf = 0

    def feed(self, stueck: str) -> str:
        """Gibt zurueck, was von diesem Haeppchen in den Chat gehoert."""
        if self._zustand == "roh":
            return stueck
        return "".join(self._zeichen(z) for z in stueck)

    # -- Hilfen ---------------------------------------------------------------

    def _entwerte(self, z: str) -> str:
        """Loest ein JSON-Fluchtzeichen auf und laesst LaTeX-Befehle unversehrt."""
        if self._hex is None:
            self._escape = False
            if z == "u":
                self._hex = ""
                return ""
            return _ECHTE_FLUCHT.get(z, "\\" + z)
        if z not in _HEX:
            # Keine vier Hex-Ziffern, also war es doch ein LaTeX-Befehl.
            ziffern, self._hex = self._hex, None
            return "\\u" + ziffern + z
        self._hex += z
        if len(self._hex) < 4:
            return ""
        ziffern, self._hex = self._hex, None
        return self._aus_hex(ziffern)

    def _aus_hex(self, ziffern: str) -> str:
        """Setzt aus vier Hex-Ziffern ein Zeichen zusammen, notfalls aus zwei Haelften."""
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
        """Liest eine Zeichenkette ein und gibt sie zurueck, sobald sie zu Ende ist."""
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
        """Merkt sich, warum hier Schluss ist, damit der Aufrufer den Strom beendet."""
        if not self.fertig:
            self.fertig = True
            self.grund = grund

    def _leerlauf_pruefen(self, z: str) -> None:
        """Zaehlt Leerraum zwischen den Feldern und meldet ein steckengebliebenes Modell."""
        if self._offen or not z.isspace():
            self._leerlauf = 0
            return
        self._leerlauf += 1
        if self._leerlauf > LEERLAUF_MAX:
            logger.warning("leerlauf: modell schreibt nur noch leerraum in zustand {}",
                           self._zustand)
            self._schluss_melden("leerlauf")

    def _zeige(self, text: str) -> str:
        """Haelt zurueck, was ueber die Obergrenze der Eintraege hinausgeht."""
        if self._max is None or self._eintraege <= self._max:
            return text
        self.genug = True
        return ""

    def _absage(self, bruecke: str = "") -> str:
        """Fuegt Absage und Brueckenteil zu einem einzigen Satz zusammen."""
        luecke, self._luecke = self._luecke, ""
        if not luecke:
            return (self._schluss(self._gross(bruecke), ":") + "\n") if bruecke else ""
        # Nur melden, nicht reparieren: einen Satz kann der Code nur auf Deutsch bauen.
        if is_bare_term(luecke):
            logger.warning("absage: begriff statt satz im feld, {!r}", luecke)
        # gap traegt die gerenderte Form, sonst findet chat.py die Absage-Zeile nicht mehr.
        if not bruecke:
            self.gap = self._schluss(self._gross(luecke), ".")
            return self.gap + "\n\n"
        # Das Komma setzt der Zusammenbau, ein eigenes am Satzende waere das zweite.
        self.gap = self._gross(luecke.rstrip().rstrip(".,"))
        return self._schluss(self.gap + ", " + bruecke.lstrip(" ,"), ":") + "\n"

    @staticmethod
    def _gross(satz: str) -> str:
        """Satzanfang gross, weil die Kleinschreib-Regel der Bruecke auf die Absage abfaerbt."""
        return satz[:1].upper() + satz[1:]

    @staticmethod
    def _schluss(satz: str, zeichen: str) -> str:
        """Setzt das fehlende Satzende, das Modell laesst es beim Streamen oft weg."""
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
            # Kein JSON: das Schema wurde ignoriert, alles faellt unveraendert durch.
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
