"""How the pickers organise monsters and items.

Monsters are grouped by their class in the game's Hunter's Notes (Flying Wyverns, Brute Wyverns...)
and sorted by a threat level from 1 to 10: how hard players usually find the monster, roughly the
order the game introduces it (Great Jaggi 1 ... Alatreon 10). This is an editorial ranking, not a
game value; the strength of a monster in a quest comes from the quest's Health / Attack rows.

Items are grouped by the shape of their in-game icon (the game draws every potion with the same
bottle, every ore with the same rock...), which follows the game's own families closely.
"""
from __future__ import annotations

import json

from . import gamedata as G

# ------------------------------------------------------------------ monsters
MONSTER_CLASSES = ("Bird Wyverns", "Flying Wyverns", "Piscine Wyverns", "Brute Wyverns", "Leviathans",
                   "Fanged Beasts", "Fanged Wyverns", "Elder Dragons", "Small monsters", "Other")

_CLASS_BY_NAME = {
    "Bird Wyverns": ("Great Jaggi", "Great Baggi", "Great Wroggi", "Qurupeco", "Crimson Qurupeco"),
    "Flying Wyverns": ("Rathian", "Pink Rathian", "Gold Rathian", "Rathalos", "Azure Rathalos",
                       "Silver Rathalos", "Gigginox", "Baleful Gigginox", "Barioth", "Sand Barioth",
                       "Nargacuga", "Green Nargacuga", "Lucent Nargacuga", "Diablos", "Black Diablos"),
    "Piscine Wyverns": ("Royal Ludroth", "Purple Ludroth", "Gobul", "Agnaktor", "Glacial Agnaktor",
                        "Plesioth", "Green Plesioth"),
    "Brute Wyverns": ("Barroth", "Jade Barroth", "Uragaan", "Steel Uragaan", "Deviljho", "Savage Deviljho",
                      "Duramboros", "Rust Duramboros", "Brachydios"),
    "Leviathans": ("Lagiacrus", "Ivory Lagiacrus", "Abyssal Lagiacrus", "Volvidon", "Nibelsnarf"),
    "Fanged Beasts": ("Arzuros", "Lagombi"),
    "Fanged Wyverns": ("Zinogre", "Stygian Zinogre"),
    "Elder Dragons": ("Ceadeus", "Goldbeard Ceadeus", "Jhen Mohran", "Hallowed Jhen Mohran", "Alatreon",
                      "Dire Miralis"),
}
# 1 = first hunts of the game ... 10 = the hardest fights
_THREAT_BY_NAME = {
    "Great Jaggi": 1, "Arzuros": 1, "Great Baggi": 2, "Great Wroggi": 2, "Lagombi": 2, "Qurupeco": 2,
    "Royal Ludroth": 2, "Barroth": 3, "Volvidon": 3, "Gobul": 3, "Nibelsnarf": 3, "Rathian": 4,
    "Gigginox": 4, "Barioth": 5, "Lagiacrus": 5, "Zinogre": 5, "Duramboros": 5, "Agnaktor": 5,
    "Nargacuga": 5, "Plesioth": 5, "Crimson Qurupeco": 5, "Jade Barroth": 5, "Purple Ludroth": 5,
    "Uragaan": 6, "Rathalos": 6, "Diablos": 6, "Baleful Gigginox": 6, "Sand Barioth": 6,
    "Green Nargacuga": 6, "Pink Rathian": 6, "Jhen Mohran": 6, "Ceadeus": 7, "Brachydios": 7,
    "Azure Rathalos": 7, "Steel Uragaan": 7, "Glacial Agnaktor": 7, "Ivory Lagiacrus": 7,
    "Green Plesioth": 7, "Rust Duramboros": 7, "Black Diablos": 8, "Lucent Nargacuga": 8,
    "Stygian Zinogre": 8, "Deviljho": 8, "Hallowed Jhen Mohran": 8, "Gold Rathian": 9,
    "Silver Rathalos": 9, "Abyssal Lagiacrus": 9, "Savage Deviljho": 9, "Goldbeard Ceadeus": 9,
    "Alatreon": 10, "Dire Miralis": 10,
}
_SMALL = {"Aptonoth", "Epioth", "Kelbi", "Popo", "Rhenoplos", "Slagtoth", "Slagtoth (Red)", "Anteka",
          "Bullfango", "Gargwa", "Altaroth", "Bnahabra (Blue)", "Bnahabra (Red)", "Bnahabra (Green/Brown)",
          "Jaggi", "Jaggia", "Baggi", "Wroggi", "Ludroth", "Uroktor", "Delex", "Giggi", "Felyne",
          "Melynx", "Fish"}

_EN = {int(k): v["name"] for k, v in json.loads((G.DATA_DIR / "monsters.json")
                                               .read_text(encoding="utf-8"))["monsters"].items()}
MONSTER_CLASS: dict[int, str] = {}
MONSTER_THREAT: dict[int, int] = {}
for _em, _name in _EN.items():
    cls = next((c for c, names in _CLASS_BY_NAME.items() if _name in names), None)
    if cls is None:
        cls = "Small monsters" if _name in _SMALL else "Other"
    MONSTER_CLASS[_em] = cls
    if _name in _THREAT_BY_NAME:
        MONSTER_THREAT[_em] = _THREAT_BY_NAME[_name]


def english_name(em: int) -> str:
    """The monster's English name (to search in English when the editor is in French)."""
    return _EN.get(em, "")


def threat_text(em: int) -> str:
    """'★★★☆☆' (1 to 5 stars from the 1-10 threat level), or '' for small monsters."""
    t = MONSTER_THREAT.get(em)
    if not t:
        return ""
    n = (t + 1) // 2
    return "★" * n + "☆" * (5 - n)


THREAT_TIERS = ((1, 2, "Beginner"), (3, 4, "Low Rank"), (5, 6, "High Rank"), (7, 8, "G Rank"),
                (9, 10, "Hardest"))


def threat_tier(em: int) -> str | None:
    t = MONSTER_THREAT.get(em)
    for lo, hi, name in THREAT_TIERS:
        if t and lo <= t <= hi:
            return name
    return None


# ------------------------------------------------------------------- items
ITEM_GROUPS = ("Healing & buffs", "Food & bait", "Bombs, traps & throwables", "Tools", "Ammo & coatings",
               "Plants & mushrooms", "Bugs", "Ore & stones", "Fish", "Monster parts", "Rare parts & gems",
               "Eggs", "Coins, tickets & books", "Jewels & decorations", "Other")
_SHAPE_GROUP = {
    25: 0, 36: 0, 4: 1, 5: 1, 20: 1,
    1: 2, 2: 2, 3: 2, 7: 2, 9: 2, 18: 2, 22: 2, 23: 2, 39: 2, 41: 2,
    8: 3, 12: 3, 14: 3, 17: 3, 30: 3, 31: 3, 48: 3, 49: 3,
    27: 4, 29: 4, 42: 4, 43: 4,
    13: 5, 16: 5, 19: 5, 60: 5, 21: 6, 28: 7, 6: 8,
    10: 9, 11: 9, 15: 9, 24: 9, 32: 9, 33: 9, 63: 9,
    44: 10, 52: 10, 55: 10, 26: 11,
    34: 12, 35: 12, 37: 12, 38: 12, 50: 12, 53: 12, 54: 12,
    40: 13, 51: 13,
}


def item_group(item_id: int, icons_index: dict) -> str:
    """Family of an item, from the shape of its icon (data/icons.json)."""
    slot = icons_index.get("items", {}).get(str(item_id))
    combos = icons_index.get("item_combos") or []
    if slot is None or slot >= len(combos):
        return ITEM_GROUPS[-1]
    return ITEM_GROUPS[_SHAPE_GROUP.get(combos[slot][0], len(ITEM_GROUPS) - 1)]
