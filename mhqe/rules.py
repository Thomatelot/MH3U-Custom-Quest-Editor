"""Who can join a quest, and whether it takes place by day or by night.

Requirements (found by mh3u-quest-studio on the Wii U version, checked here on every 3DS quest):
* special_cond and special_cond2 are the two RULES the game enforces when the quest is started or
  joined. Both index a 24-entry table: 0 = no rule, 1-11 = online players can not join, 12 = no
  armor or talismans, 13-15 = at most 1-3 players, 16-23 = Hunter Rank 2-9 or higher.
* special_flag only picks the line the quest board shows (the game's quest message 42 + flag).
  The 3DS quests always pair them the same way (flag 3 with rule 17 = HR 3, flag 18 with rule 12 =
  no armor, flag 9 with rules 17 + 13 = HR 3 and solo...).

Day or night: every quest of the game sets exactly one of two category bits, 0x10000 (day) or
0x20000 (night); the night quests are the ones whose texts speak of the night ("Narg at Nite",
"Moonlit Tryst", "Howl at the Moon", Moga (Night) quests). The arenas are always by day.
"""
from __future__ import annotations

from collections import namedtuple

from . import gamedata as G

COND_COUNT = 24
DAY_BIT, NIGHT_BIT = 0x10000, 0x20000

Req = namedtuple("Req", "hr players naked")
NO_REQ = Req(None, 4, False)

# The quest board lines, as the 3DS game writes them (Quest_eng / Quest_fre messages 42-69).
_TEXT_EN = (
    ["None."]
    + [f"Must be HR {n} or higher to initiate/join." for n in range(1, 9)]
    + [f"Must be HR {hr} or higher to join. Max participants: {p}" for p in (1, 2, 4) for hr in (3, 6, 8)]
    + ["Must remove all armor and talismans to initiate/join.",
       "Must be HR 3 or higher to join. No armor or talismans.",
       "Must be HR 6 or higher to join. No armor or talismans."]
    + ["Must bring Cha-Cha & Kayamba."] * 2
    + ["Must bring Cha-Cha, Kayamba & Unfortunate Mask (on Kayamba)."] * 2
    + [f"No HR restrictions. Max participants: {p}" for p in (1, 2, 4)])
_TEXT_FR = (
    ["Aucune."]
    + [f"Rang {n} ou plus pour commencer/rejoindre." for n in range(1, 9)]
    + [f"Rg {hr} ou + pour rejoindre. Max {p} participant{'s' if p > 1 else ''}."
       for p in (1, 2, 4) for hr in (3, 6, 8)]
    + ["Retirez armures et talismans pour comm./rejoin.",
       "Rg 3 ou + pour rejoindre. Ni armures ni talismans.",
       "Rg 6 ou + pour rejoindre. Ni armures ni talismans."]
    + ["Emmenez Cha-Cha & Kayamba."] * 2
    + ["Emmenez Cha-Cha & Kayamba avec masque malchanceux."] * 2
    + [f"Pas de restriction de rang. Max {p} participant{'s' if p > 1 else ''}." for p in (1, 2, 4)])
# what each line claims (the Cha-Cha lines claim nothing these rules can check)
CLAIMS = ([NO_REQ, NO_REQ] + [Req(n, 4, False) for n in range(2, 9)]
          + [Req(hr, p, False) for p in (1, 2, 4) for hr in (3, 6, 8)]
          + [Req(None, 4, True), Req(3, 4, True), Req(6, 4, True)]
          + [NO_REQ] * 4
          + [Req(None, p, False) for p in (1, 2, 4)])
assert len(_TEXT_EN) == len(_TEXT_FR) == len(CLAIMS) == 28
_NO_AUTO = {1, 21, 22, 23, 24}            # never picked automatically

HR_CHOICES = [None] + list(range(2, 10))   # Hunter Rank minimum (9 has no board line)
PLAYER_CHOICES = [4, 1, 2, 3]


def board_text(flag: int) -> str:
    from . import i18n
    lines = _TEXT_FR if i18n.LANG == "fr" else _TEXT_EN
    return lines[flag] if 0 <= flag < len(lines) else "(nothing shown)"


def rules_of(c1: int, c2: int) -> Req:
    conds = (c1, c2)
    hr = max((c - 14 for c in conds if 16 <= c < COND_COUNT), default=None)
    players = min((c - 12 for c in conds if 13 <= c <= 15), default=4)
    return Req(hr, players, 12 in conds)


def conds_for(req: Req) -> tuple[int, int] | None:
    """The two rule values for these requirements, or None if they need three rules."""
    out = []
    if req.hr:
        out.append(14 + req.hr)
    if req.players < 4:
        out.append(12 + req.players)
    if req.naked:
        out.append(12)
    if len(out) > 2:
        return None
    out += [0] * (2 - len(out))
    return out[0], out[1]


def flag_for(req: Req, current: int) -> int:
    """The board line for these rules: the current one if it already says exactly that, else the
    first line that does, else the closest one that claims nothing false (HR line, or 'None.')."""
    if 0 <= current < len(CLAIMS) and CLAIMS[current] == req:
        return current
    exact = next((f for f, r in enumerate(CLAIMS) if r == req and f not in _NO_AUTO), None)
    if exact is not None:
        return exact
    if req.hr and 2 <= req.hr <= 8:
        return 1 + req.hr - 1 + 0 if False else req.hr     # 'Must be HR n or higher' lines are flags 1-8
    return 0


def describe(req: Req) -> str:
    parts = []
    if req.hr:
        parts.append(f"HR {req.hr} or higher")
    if req.players < 4:
        parts.append(f"at most {req.players} player" + ("s" if req.players > 1 else ""))
    if req.naked:
        parts.append("no armor or talismans")
    return ", ".join(parts) or "anyone can join"


def problems(flag: int, c1: int, c2: int) -> list[str]:
    out = []
    for i, c in enumerate((c1, c2), 1):
        if c >= COND_COUNT:
            out.append(f"Rule {i} = {c} is past the end of the game's table (0-{COND_COUNT - 1}).")
        elif 1 <= c <= 11:
            out.append(f"Rule {i} = {c}: nobody will be able to join this quest online.")
    want = rules_of(c1, c2)
    if not 0 <= flag < len(CLAIMS):
        if want != NO_REQ:
            out.append(f"The quest board shows no requirement, but the rules are: {describe(want)}.")
    elif CLAIMS[flag] != want and flag not in (21, 22, 23, 24):
        out.append(f"The quest board says \"{_TEXT_EN[flag]}\" but the rules are: {describe(want)}.")
    return out


# ------------------------------------------------------------- day / night
def is_night(q) -> bool:
    return bool(q.get("category") & NIGHT_BIT)


def set_night(q, night: bool) -> None:
    cat = q.get("category") & ~(DAY_BIT | NIGHT_BIT)
    q.set("category", cat | (NIGHT_BIT if night else DAY_BIT))


# maps whose game quests are all by day (night untested there)
DAY_ONLY_MAPS = {6, 7, 8, 9, 10, 11, 12, 15}


def time_warning(q) -> str | None:
    if is_night(q) and q.get("map") in DAY_ONLY_MAPS:
        return (f"No quest of the game takes place at night on {G.map_name(q.get('map'))}: "
                "untested, the map may have no night version.")
    return None
