"""What opens a base-game quest, and what a cleared quest opens (Village and Port).

Read from the function that builds the quest counter's lists (0x623EC8 in the EU/US 1.0 code):

* The game does not hold a list of the Village or Port quests: it loads EVERY file of
  quest00.arc and sorts the quests by their number (1000-10999 Village, 11000-12899 Port) and
  their star rank. A file added to the archive is listed like the others.

* After its objectives a quest file holds three values (the game's OpenFlag block):
      need    64 bits: the groups this quest looks at
      give    64 bits: the groups this quest counts in once it is cleared
      count   the quest is listed when the cleared quests of its 'need' groups, added up,
              reach this number (0 = always listed)
  The four key quests of the Port's 1-star rank 'give' group 3 and the urgent quest 12201
  'needs' group 3 four times: this is all that makes a quest a key quest. The counts are made
  per hub (a Village quest never counts for the Port).

* "Cleared" is a bit in the save whose position is the quest's place in the game's quest list
  (see gamecode.py). A quest that is not in that list is never cleared: a new quest only counts
  once the Monster pack has registered its number.
"""
from __future__ import annotations

import json
import struct

from . import gamedata as G

FMT = "<QQB"
VILLAGE, PORT = (1000, 11000), (11000, 12900)
URGENT = {"village": (2000, 11000), "port": (12000, 12900)}
# number ranges by rank: the game puts a quest in the list of its star rank only inside them
BRACKETS = {"village": [(1000, 1600, "low rank, 1 to 5 stars"), (1600, 2000, "high rank, 6 to 9 stars")],
            "port": [(11000, 11300, "low rank, 1 and 2 stars"), (11300, 11600, "high rank, 3 to 5 stars"),
                     (11600, 12000, "G rank, 6 to 8 stars")]}


def hub(no: int) -> str | None:
    return "village" if VILLAGE[0] <= no < VILLAGE[1] else "port" if PORT[0] <= no < PORT[1] else None


def is_urgent(no: int) -> bool:
    h = hub(no)
    return h is not None and URGENT[h][0] <= no < URGENT[h][1]


def _pos(q):
    pos = getattr(q, "_rest_off", None)
    if pos is None or pos + 4 + 17 > len(q.data):
        return None
    return pos + 4                                   # after the two Challenge rank times


def read(q) -> tuple[int, int, int]:
    """(need, give, count); zeros for a record without the block."""
    p = _pos(q)
    return struct.unpack_from(FMT, q.data, p) if p is not None else (0, 0, 0)


def write(q, need: int, give: int, count: int) -> bool:
    p = _pos(q)
    if p is None:
        return False
    struct.pack_into(FMT, q.data, p, need & (2 ** 64 - 1), give & (2 ** 64 - 1), max(0, min(count, 255)))
    return True


def bits(mask: int) -> list[int]:
    return [i for i in range(64) if mask >> i & 1]


def _same_hub(quests: dict, h: str) -> dict:
    return {no: q for no, q in quests.items() if hub(no) == h}


def urgents(quests: dict, h: str) -> list[int]:
    """Urgent quests of a hub that wait for key quests."""
    return sorted(no for no, q in _same_hub(quests, h).items()
                  if is_urgent(no) and read(q)[2] > 0 and keys_of(quests, no))


def key_bit(quests: dict, urgent_no: int) -> int | None:
    """The group a new key quest of this urgent quest should count in: one that the urgent quest
    needs, that no other quest needs (so nothing else opens early), and that is not the 'previous
    urgent quest' group 63."""
    h = hub(urgent_no)
    need = read(quests[urgent_no])[0]
    cand = [b for b in bits(need) if b != 63] or bits(need)
    others = 0
    for no, q in _same_hub(quests, h).items():
        if no != urgent_no:
            others |= read(q)[0]
    alone = [b for b in cand if not others >> b & 1]
    return (alone or cand or [None])[0]


def key_for(quests: dict, no: int) -> list[int]:
    """Urgent quests this quest is a key quest of."""
    give = read(quests[no])[1]
    return [u for u in urgents(quests, hub(no) or "") if u != no and read(quests[u])[0] & give]


def keys_of(quests: dict, urgent_no: int) -> list[int]:
    need = read(quests[urgent_no])[0]
    return sorted(no for no, q in _same_hub(quests, hub(urgent_no)).items()
                  if no != urgent_no and read(q)[1] & need)


def set_key(quests: dict, no: int, urgent_no: int | None) -> list[int]:
    """Make quest 'no' a key quest of 'urgent_no' (None = of no urgent quest). The urgent quest's
    count follows, so it waits for one quest more (or less). Returns the numbers of the quests
    that changed."""
    q, changed = quests[no], []
    need, give, count = read(q)
    for u in key_for(quests, no):
        if u == urgent_no:
            return []
        un, ug, uc = read(quests[u])
        shared = bits(un & give)
        give &= ~un
        write(quests[u], un, ug, max(1, uc - len(shared)))
        changed.append(u)
    if urgent_no is not None:
        b = key_bit(quests, urgent_no)
        if b is None:
            return changed
        give |= 1 << b
        un, ug, uc = read(quests[urgent_no])
        write(quests[urgent_no], un, ug, uc + 1)
        changed.append(urgent_no)
    write(q, need, give, count)
    return changed + [no]


def openers(quests: dict, no: int) -> list[int]:
    """Quests whose clearing counts for this quest's 'need' groups."""
    need = read(quests[no])[0]
    return sorted(n for n, q in _same_hub(quests, hub(no) or "").items() if n != no and read(q)[1] & need)


def describe(quests: dict, no: int) -> list[str]:
    """Plain sentences for the editor."""
    q = quests[no]
    need, _give, count = read(q)
    out = []
    if count:
        op = openers(quests, no)
        names = ", ".join(f"'{quests[n].get_text('name')}'" for n in op[:6]) + (", ..." if len(op) > 6 else "")
        if count >= len(op) > 0:
            out.append(f"Listed once you have cleared: {names}.")
        elif op:
            out.append(f"Listed once you have cleared {count} of: {names}.")
        else:
            out.append("Opened by the game in another way (no quest of this hub counts for it; for the G rank "
                       "quests it is the Hunter Rank). Not editable here.")
    else:
        out.append("Always listed in its star rank.")
    for u in key_for(quests, no):
        out.append(f"Key quest: needed to open the urgent quest '{quests[u].get_text('name')}'.")
    return out


# ------------------------------------------------------------- the game's quest list
def game_numbers() -> set[int]:
    try:
        return set(json.loads((G.DATA_DIR / "master_quests.json").read_text(encoding="utf-8"))["numbers"])
    except (OSError, ValueError, KeyError):
        return set()


def can_be_cleared(no: int, pack: dict | None = None) -> bool:
    """True if the game (or the built Monster pack) has this number in its quest list."""
    return no in game_numbers() or str(no) in (pack or {}).get("quests", {})


def suggest_number(quests: dict, h: str, star: int) -> int | None:
    """A free number the game will list in this hub and star rank, following the game's own
    habit (Port 3 stars = 113xx...)."""
    base = (1000 if h == "village" else 11000) + 100 * star
    lo, hi = next(((a, b) for a, b, _t in BRACKETS[h] if a <= base < b), (None, None))
    if lo is None:
        return None
    for no in list(range(base + 20, min(base + 100, hi))) + list(range(base + 1, base + 20)):
        if no not in quests and lo <= no < hi:
            return no
    return None


def problems(quests: dict, no: int, pack: dict | None = None) -> list[tuple[str, str]]:
    q = quests[no]
    h = hub(no)
    if h is None:
        return []
    out = []
    star = q.get("star")
    if not is_urgent(no):
        br = next(((a, b, t) for a, b, t in BRACKETS[h] if a <= no < b), None)
        want = next(((a, b, t) for a, b, t in BRACKETS[h] if a <= (1000 if h == "village" else 11000) + 100 * star < b), None)
        if br and want and br != want:
            out.append(("warning", f"Quest number {no} belongs to the {br[2]} of the {h.capitalize()}, but the "
                                   f"quest has {star} stars: the game sorts quests by their number first, so "
                                   "it may not be listed where you expect."))
    need, give, count = read(q)
    if not can_be_cleared(no, pack):
        level = "error" if give else "warning"
        out.append((level, f"Quest {no} is not in the game's quest list, so the game never records it as cleared"
                    + (" and the quests waiting for it never open" if give else "")
                    + ". Build and install the Monster pack again: it registers the new quests."))
    if is_urgent(no) and count and keys_of(quests, no):
        have = sum(len(bits(read(quests[k])[1] & need)) for k in keys_of(quests, no))
        if have < count:
            out.append(("error", f"This urgent quest waits for {count} key quests but only {have} exist: "
                                 "it can never open."))
    return out
