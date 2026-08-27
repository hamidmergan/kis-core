"""Which slides go into the screencast and which keep their old audio."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Auswahl:
    """The three views on the same decision so nobody recomputes it."""

    clip_folien: list[int]
    ausgeschlossen: set[int]
    alter_ton_erlaubt: set[int]


def folien_auswahl(
    anzahl: int,
    video_folien: list[int] | None,
    neu_vertonen: list[int] | None,
) -> Auswahl:
    """None means all slides, numbers outside the range are dropped."""
    alle = set(range(anzahl))
    dabei = alle if video_folien is None else {i for i in video_folien if i in alle}
    neu = {i for i in (neu_vertonen or []) if i in alle}
    return Auswahl(
        clip_folien=sorted(dabei),
        ausgeschlossen=alle - dabei,
        alter_ton_erlaubt=dabei - neu,
    )


def clip_paare(clip_folien: list[int], num_slides: int) -> list[tuple[int, int]]:
    """Per clip the build position and the slide number that belong together."""
    return list(enumerate(i for i in clip_folien if i < num_slides))


def ton_plaetze(anzahl: int, clip_folien: list[int]) -> list[bool]:
    """True only where new audio goes, otherwise the old one stays."""
    dabei = set(clip_folien)
    return [i in dabei for i in range(anzahl)]


def zu_sprechende_folien(clip_folien: list[int], scripts: list[str], schon_da: set[int]) -> int:
    """Counts the slides that still need real audio, neither pooled nor empty."""
    return sum(1 for i in clip_folien if i not in schon_da and scripts[i].strip())
