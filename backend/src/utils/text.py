import copy

from lxml import etree

from src.services.translation import TranslationService

TAB_PLACEHOLDER = "\u27e8TAB\u27e9"
NL_PLACEHOLDER = "\u27e8NL\u27e9"


def _encode_whitespace(text: str) -> tuple[str, str, str]:
    """Extract leading/trailing whitespace and encode tabs and newlines."""
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    inner = text.strip()
    inner = inner.replace("\t", TAB_PLACEHOLDER).replace("\n", NL_PLACEHOLDER)
    return leading, inner, trailing


def _decode_whitespace(text: str, leading: str, trailing: str) -> str:
    """Restore tabs and newlines and re-attach surrounding whitespace."""
    text = text.replace(TAB_PLACEHOLDER, "\t").replace(NL_PLACEHOLDER, "\n")
    return leading + text + trailing


# ── Single-text helpers (used by Markdown, LaTeX, filename translation) ──────

# ── Batch helpers for PPTX / DOCX (1 DeepL call per document) ───────────────

class _RunRef:
    """Holds a reference to a run or paragraph and the encoded text to translate.

    ``also_clear`` sind weitere Runs, deren Text in diesen hier eingeflossen ist.
    Sie werden beim Zurückschreiben geleert.
    """
    __slots__ = ("obj", "attr", "leading", "trailing", "encoded", "also_clear")

    def __init__(self, obj, attr: str, leading: str, encoded: str, trailing: str, also_clear=()):
        self.obj = obj
        self.attr = attr
        self.leading = leading
        self.encoded = encoded
        self.trailing = trailing
        self.also_clear = list(also_clear)


# Diese Angaben kommen von Rechtschreibprüfung und Spracherkennung, nicht von
# der Formatierung. PowerPoint zerlegt Absätze laufend an genau diesen Stellen.
_VOLATILE_RPR_ATTRS = ("lang", "altLang", "dirty", "err", "noProof", "smtClean", "smtId")
_VOLATILE_RPR_CHILDREN = ("lang", "noProof")


def _format_key(run) -> bytes:
    """Formatierung eines Runs als Vergleichsschlüssel, ohne Prüf- und Sprachmarken."""
    element = getattr(run, "_r", None)
    if element is None:
        return b""
    run_pr = next((c for c in element if etree.QName(c).localname == "rPr"), None)
    if run_pr is None:
        return b""
    clone = copy.deepcopy(run_pr)
    for attr in _VOLATILE_RPR_ATTRS:
        clone.attrib.pop(attr, None)
    for child in list(clone):
        if etree.QName(child).localname in _VOLATILE_RPR_CHILDREN:
            clone.remove(child)
    return etree.tostring(clone)


def _group_runs_by_format(runs: list) -> list[list]:
    """Aufeinanderfolgende Runs mit gleicher Formatierung zusammenfassen.

    PowerPoint und Word zerschneiden einen Satz oft mitten im Wort, sobald die
    Rechtschreibprüfung anspringt. Übersetzt man diese Bruchstücke einzeln,
    stimmt die Wortstellung nicht mehr. Echte Formatwechsel, etwa ein fett
    gesetztes Wort, bleiben eigene Gruppen und behalten ihr Aussehen.
    """
    groups: list[list] = []
    last_key: bytes | None = None
    for run in runs:
        key = _format_key(run)
        if groups and key == last_key:
            groups[-1].append(run)
        else:
            groups.append([run])
        last_key = key
    return groups


def collect_paragraph_runs(paragraph, refs: list[_RunRef]) -> None:
    """
    Collect all translatable text pieces from a paragraph into refs.
    Newlines and tabs are encoded as placeholders so DeepL sees a single line.
    """
    runs = list(paragraph.runs)

    if not runs:
        text = paragraph.text
        if text and text.strip():
            leading, encoded, trailing = _encode_whitespace(text)
            refs.append(_RunRef(paragraph, "text", leading, encoded, trailing))
        return

    for group in _group_runs_by_format(runs):
        text = "".join(run.text or "" for run in group)
        if not text.strip():
            continue
        leading, encoded, trailing = _encode_whitespace(text)
        refs.append(_RunRef(group[0], "text", leading, encoded, trailing, also_clear=group[1:]))


def apply_translations(refs: list[_RunRef], translated: list[str]) -> None:
    """Write translated strings back to their source objects."""
    if len(translated) != len(refs):
        # Früher hat zip() den Rest still stehen lassen. Das Ergebnis war eine
        # halb übersetzte Datei ohne jeden Hinweis.
        raise ValueError(
            f"Übersetzer lieferte {len(translated)} von {len(refs)} Texten zurück"
        )
    for ref, t in zip(refs, translated):
        setattr(ref.obj, ref.attr, _decode_whitespace(t, ref.leading, ref.trailing))
        for run in ref.also_clear:
            run.text = ""


def translate_refs(
    refs: list[_RunRef], source_lang: str, target_lang: str, service: TranslationService
) -> None:
    """Alle gesammelten Textstellen übersetzen und zurückschreiben.

    Gleiche Texte gehen nur einmal an den Anbieter. In einer Präsentation
    wiederholt sich sehr viel, das spart Kontingent und Anfragen.
    """
    if not refs:
        return
    texts = [r.encoded for r in refs]
    unique = list(dict.fromkeys(texts))
    translated_unique = service.translate_batch(unique, source_lang, target_lang)
    if len(translated_unique) != len(unique):
        raise ValueError(
            f"Übersetzer lieferte {len(translated_unique)} von {len(unique)} Texten zurück"
        )
    by_source = dict(zip(unique, translated_unique))
    apply_translations(refs, [by_source[t] for t in texts])


# ── Legacy single-paragraph helper (used by Markdown / LaTeX translators) ───

