"""Der Aufbau der Rechtetabelle: zwei Kapitel, darunter die Gruppen der Seitenleiste.

Vorher lagen 17 Zeilen in einer einzigen Gruppe "Einstellungen", und die vier
Zeilen zur Statistik standen an drei verschiedenen Stellen. Diese Tests halten
fest, dass beim Umsortieren keine Zeile verloren geht und keine doppelt steht.
"""

from src.permissions_registry import (
    ALL_PERMISSION_KEYS,
    CHAPTER_MANAGE,
    CHAPTER_USE,
    GROUP_CHAPTER,
    GROUPS,
    PERM_SET_AIA_USAGE,
    PERM_SET_STATS_MODELS,
    PERM_SET_STATS_USERS,
    PERM_SET_TOOLS_STATS,
    PERMISSION_GROUPS,
)
from src.routes.admin import roles as roles_route

ADMIN = {"role": "admin", "email": "a@th-luebeck.de"}


def test_every_permission_sits_in_exactly_one_group():
    placed = [key for group in GROUPS for key in PERMISSION_GROUPS[group]]

    assert sorted(placed) == sorted(ALL_PERMISSION_KEYS)
    assert len(placed) == len(set(placed))


def test_no_group_is_empty():
    assert all(PERMISSION_GROUPS[group] for group in GROUPS)


def test_groups_stand_in_two_chapters_in_display_order():
    assert [(GROUP_CHAPTER[g], g) for g in GROUPS] == [
        (CHAPTER_USE, "aia"),
        (CHAPTER_USE, "tools"),
        (CHAPTER_MANAGE, "set.werkzeuge"),
        (CHAPTER_MANAGE, "set.assistent"),
        (CHAPTER_MANAGE, "set.statistik"),
        (CHAPTER_MANAGE, "set.anbieter"),
        (CHAPTER_MANAGE, "set.nutzer"),
        (CHAPTER_MANAGE, "set.system"),
        (CHAPTER_MANAGE, "set.mascot"),
    ]


def test_the_four_statistics_rights_stand_together():
    assert PERMISSION_GROUPS["set.statistik"] == (
        PERM_SET_STATS_USERS,
        PERM_SET_TOOLS_STATS,
        PERM_SET_AIA_USAGE,
        PERM_SET_STATS_MODELS,
    )


async def test_the_route_hands_each_group_its_chapter(monkeypatch):
    monkeypatch.setattr(roles_route.db, "list_custom_roles", lambda: [])

    body = await roles_route.list_roles(admin=ADMIN)

    assert [(g["chapter"], g["key"]) for g in body["groups"]] == [
        (GROUP_CHAPTER[g], g) for g in GROUPS
    ]
