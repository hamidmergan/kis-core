"""Calendar colours per person: fixed palette, never two groups on the same colour while the palette lasts."""

import random
from collections import Counter

# Dark enough that white text on top stays readable in light and dark mode.
PALETTE = (
    "#1D4ED8",  # blue
    "#0369A1",  # sky
    "#0F766E",  # teal
    "#15803D",  # green
    "#4D7C0F",  # lime
    "#A16207",  # gold
    "#C2410C",  # orange
    "#B91C1C",  # red
    "#9D174D",  # raspberry
    "#A21CAF",  # fuchsia
    "#7E22CE",  # purple
    "#4338CA",  # indigo
    "#4F7A91",  # slate blue
    "#57534E",  # stone
    "#854D0E",  # brown
)

# Group key of private appointments, a workspace uuid never looks like this.
PRIVAT = "privat"

# Private appointments keep their former colour as long as it is free.
_PRIVAT_VORZUG = 12


def vergeben(gruppen: list[str], vorhanden: dict[str, int], rng: random.Random | None = None) -> dict[str, int]:
    """Colours for the groups that have none yet, picked at random among the free ones."""
    rng = rng or random.Random()
    belegt = Counter(vorhanden[g] for g in gruppen if g in vorhanden)
    neu: dict[str, int] = {}
    for g in gruppen:
        if g in vorhanden:
            continue
        frei = [i for i in range(len(PALETTE)) if belegt[i] == 0]
        if g == PRIVAT and _PRIVAT_VORZUG in frei:
            farbe = _PRIVAT_VORZUG
        elif frei:
            farbe = rng.choice(frei)
        else:
            # More groups than colours, then the least used colour repeats.
            wenigste = min(belegt[i] for i in range(len(PALETTE)))
            farbe = rng.choice([i for i in range(len(PALETTE)) if belegt[i] == wenigste])
        belegt[farbe] += 1
        neu[g] = farbe
    return neu


def waehlen(gruppen: list[str], vorhanden: dict[str, int], gruppe: str, farbe: int) -> dict[str, int]:
    """Gives the group its colour, a group already holding it takes over the old one."""
    aenderungen = {gruppe: farbe}
    alt = vorhanden.get(gruppe)
    for g in gruppen:
        if g != gruppe and vorhanden.get(g) == farbe and alt is not None:
            aenderungen[g] = alt
    return aenderungen
