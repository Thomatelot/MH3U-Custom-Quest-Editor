"""The fights the game scripts around a ship or a ruin: Jhen Mohran on the Great Desert (the
Dragonship) and Ceadeus on the Underwater Ruin.

Read from the game's own quests (3DS romfs, EU and US alike):

  #01712 Rumble in the Great Desert     category 0x10010001  A = 0x2515 Jhen Mohran 50
                                                             B = 0x2000 id 4, 1000   pattern 0
  #11510 [Canteen] Desert Rumble!       the same
  #11823 Festival on the Sea of Sand    category 0x10020001  A = 0x2515 Hallowed Jhen 50
                                                             B = 0x2000 id 4, 1300   pattern 0
  #01515 The Decisive Battle            category 0x10001     A = 0x4014 Ceadeus 40
          (Underwater Ruin)                                  B = 0x0101 Ceadeus 1    pattern 2

On the Great Desert the second objective is not a goal (pattern 0 = single objective): its
count is the Dragonship's integrity, which the failure text names ("Reward or Dragonship
Integrity hits 0, or time expires."). A desert quest without it starts with an integrity of 0,
which fits what a player saw: the Dragonship destroyed and the quest failed as soon as it began.
Category bit 0x10000000 is set in the three desert quests and in no other quest.
"""
from __future__ import annotations

DESERT, RUIN = 6, 7
SHIP_BIT = 0x10000000
JHEN = {25: 1000, 85: 1300}            # species -> the Dragonship integrity its quests use
CEADEUS = (20, 70)
JHEN_OBJ, SHIP_OBJ, CEADEUS_OBJ = 0x2515, 0x2000, 0x4014
JHEN_COUNT, SHIP_ID, CEADEUS_COUNT = 50, 4, 40
SIEGE_TYPES = (JHEN_OBJ, SHIP_OBJ, CEADEUS_OBJ)

# The desert quests' failure text, in the game's five languages (EN FR DE IT ES).
SHIP_FAILURE = ("Reward or Dragonship Integrity\r\nhits 0, or time expires.",
                "Prime ou intégrité drakkar\r\natteint 0 ou temps écoulé.",
                "Belohnung o. Drachenschf.-\r\nZustand auf 0 o. Zeit um.",
                "Premio o integrità dragoniera\r\na 0, oppure tempo scaduto.",
                "Recomp. o integr. cazadr.\r\ncae a 0, o fin tiempo.")


def jhen_of(q) -> int | None:
    """The Jhen Mohran species of the quest (25 or 85), if it has one."""
    for m in q.monsters:
        if m["Type"] in JHEN:
            return m["Type"]
    return None


def is_ship_fight(q) -> bool:
    return q.get("map") == DESERT and jhen_of(q) is not None


def ship_ok(q) -> bool:
    """True if the quest is set up like the game's desert quests."""
    em = jhen_of(q)
    if em is None:
        return False
    t1, _m1, id1, n1 = q.objective(1)
    t2, _m2, id2, n2 = q.objective(2)
    return (bool(q.get("category") & SHIP_BIT) and t1 == JHEN_OBJ and id1 == em and n1 > 0
            and t2 == SHIP_OBJ and n2 > 0 and q.get("clr_pattern") == 0)


def apply_ship(q, failure_text: bool = True) -> bool:
    """Set the quest up like the game's Dragonship fights. Returns False without a Jhen Mohran."""
    em = jhen_of(q)
    if em is None:
        return False
    q.set("category", q.get("category") | SHIP_BIT)
    q.set_objective(1, JHEN_OBJ, em, JHEN_COUNT, 0)
    q.set_objective(2, SHIP_OBJ, SHIP_ID, JHEN[em], 0)
    q.set("clr_pattern", 0)
    if failure_text:
        for lang, text in enumerate(SHIP_FAILURE):
            q.set_text("failure", text, [lang])
    return True


def problems(q) -> list[tuple[str, str]]:
    """[(level, text)] for siege set-ups the game will not run as intended."""
    out: list[tuple[str, str]] = []
    mp = q.get("map")
    t1, t2 = q.objective(1)[0], q.objective(2)[0]
    if mp == DESERT:
        if jhen_of(q) is None:
            out.append(("warning", "Every Great Desert quest of the game is a Dragonship fight against a Jhen "
                                   "Mohran. Without one, the Dragonship and its scripts are untested: try it "
                                   "in the emulator."))
        elif not ship_ok(q):
            out.append(("error", "This Great Desert quest is not set up like the game's Dragonship fights, so "
                                 "the Dragonship can be destroyed as soon as the quest starts. Use 'Set up the "
                                 "Dragonship fight' on the General tab."))
    else:
        if q.get("category") & SHIP_BIT:
            out.append(("warning", "The quest has the Dragonship flag but its map is not the Great Desert."))
        if JHEN_OBJ in (t1, t2) or SHIP_OBJ in (t1, t2):
            out.append(("error", "A Jhen Mohran / Dragonship objective is only used on the Great Desert."))
    if CEADEUS_OBJ in (t1, t2) and mp != RUIN:
        out.append(("error", "The 'Slay or repel Ceadeus' objective is only used on the Underwater Ruin; "
                             "on another map the quest may never end or fail at once."))
    return out
