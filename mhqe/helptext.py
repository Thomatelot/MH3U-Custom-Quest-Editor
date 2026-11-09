"""Texts of the info bubbles, with benchmarks taken from the game's own quests.

Every number quoted here comes from data/benchmarks.json, which
tools/build_benchmarks.py computes from the 365 base-game quests (and the
event / challenge quests of the save it was run on). Statements about what a
field *means* are marked "not confirmed" when only its use in the game's
quests is known.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import gamedata as G

_B: dict = {}
try:
    with open(Path(__file__).resolve().parent.parent / "data" / "benchmarks.json", encoding="utf-8") as _f:
        _B = json.load(_f)
except (OSError, ValueError):
    _B = {}

GROUPS: dict = _B.get("groups", {})
PER_CLASS: dict = _B.get("per_class", {})
COMMON: dict = _B.get("common_values", {})
EXAMPLES: dict = _B.get("special_examples", {})
N_BASE = _B.get("base_quests", 365)
TIERS: dict = _B.get("tiers", {})

CLASS_LABEL = {"Village": "Village", "Port LR": "Port Low Rank", "Port HR": "Port High Rank",
               "Port G": "Port G Rank", "Event": "Event quests", "Grudge": "Grudge Matches",
               "Challenge": "Challenge quests"}


# ------------------------------------------------------------------ ranks
def _order(key: str):
    hub, star = key.split()
    return (0 if hub == "Village" else 1, int(star))


def group_keys() -> list[str]:
    return sorted(GROUPS, key=_order)


def group_label(key: str) -> str:
    """'Port 7' -> 'Port 7★ (G2★)'."""
    hub, star = key.split()
    s = int(star)
    if hub == "Port":
        rank = "Low Rank" if s <= 2 else "High Rank" if s <= 5 else f"G{s - 5}★"
        return f"Port {s}★ ({rank})"
    return f"Village {s}★"


def quest_class(q) -> str:
    """Where a quest belongs in the game, from its number (same rule as
    tools/build_benchmarks.py)."""
    n, s = q.get("quest_no"), q.get("star")
    if n < 1000:
        return "Tutorial"
    if n < 3000:
        return "Village"
    if n < 13000:
        return "Port LR" if s <= 2 else "Port HR" if s <= 5 else "Port G"
    if n < 30000:
        return "Event"
    if n < 61000:
        return "Grudge"
    return "Challenge"


def rank_label(q) -> str:
    """'Village 5★', 'Port 7★ (G2★)', 'Event quest', 'Grudge Match'..."""
    c = quest_class(q)
    if c == "Village":
        return group_label(f"Village {q.get('star')}")
    if c.startswith("Port"):
        return group_label(f"Port {q.get('star')}")
    return {"Event": "Event quest", "Grudge": "Grudge Match", "Challenge": "Challenge quest",
            "Tutorial": "Training"}[c]


def group_key_for(q) -> str | None:
    """The hub / star group of the game's quests that a quest belongs to ('Port 7', 'Village 3'...):
    the group with the same hub and the nearest star rank."""
    if not GROUPS:
        return None
    hub = "Village" if quest_class(q) in ("Village", "Tutorial") else "Port"
    star = q.get("star")
    keys = [k for k in GROUPS if k.split()[0] == hub] or list(GROUPS)
    return min(keys, key=lambda k: abs(int(k.split()[1]) - star))


def default_monster_values(q) -> dict:
    """Settings of a large monster added to a quest that has none yet: the typical values of the game's
    quests of the same hub and star rank (health / attack / toughness rows, stamina, size spread...)."""
    out = dict(Settype=0, Starttype=0, Num=1, Size=100, Nando2=0, Sizeparam=0, Stamina=0)
    key = group_key_for(q)
    if key:
        hp, at, df = preset_rows(key)
        out.update(Nando_hp=hp, Nando_at=at, Nando_etc=df)
        out.update(preset_extra(key))
    else:
        out.update(Nando_hp=0, Nando_at=0, Nando_etc=0)
    return out


def preset_extra(key: str) -> dict:
    """Stamina / spread / Nando2 that the game's quests of this hub and star use."""
    g = GROUPS[key]
    out = {}
    for field, name in (("Stamina", "stamina"), ("Sizeparam", "sizeparam"), ("Nando2", "nando2")):
        if name in g:
            out[field] = g[name]
    return out


def preset_rows(key: str) -> tuple[int, int, int]:
    g = GROUPS[key]
    return g["hp_row"], g["at_row"], g["df_row"]


def nearest(kind: str, value: float) -> str:
    """'like Port 7★ (G2★)' for a multiplier (kind: hp, atk, dmg)."""
    if not GROUPS:
        return ""
    diff = {k: abs(GROUPS[k][kind] - value) for k in GROUPS}
    low = min(diff.values())
    same = sorted((k for k in GROUPS if diff[k] - low < 1e-6), key=_order)
    names = [group_label(k) for k in same]
    if len(names) > 3:
        names = names[:2] + [f"{len(names) - 2} more"]
    return "like " + ", ".join(names)



# ------------------------------------------------------------- difficulty tiers
# A stat row is compared with thresholds measured on the game's own monsters:
#   below LR  -> Low Rank      (Village 1-5, Port 1-2 star)
#   below HR  -> High Rank     (Village 6-9, Port 3-5 star)
#   below G   -> G Rank        (Port 6-8 star)
#   up to MAX -> hardest G Rank (the hardest event quests: no other quest goes higher)
#   above MAX -> Nightmare     (harder than anything in the game)
# LR / HR / G are the 90th percentile of the rows used in that rank; MAX is the highest row used
# anywhere (guild quests, Grudge Matches, challenge quests and the original event quests).
# The difficulty table grows steadily with the row number, so rows can be compared directly.
TIER_NAMES = ("Low Rank", "High Rank", "G Rank", "G Rank (hardest events)", "Nightmare")
NIGHTMARE = 4
_STAT_KEY = {"Nando_hp": "hp", "Nando_at": "at", "Nando_etc": "etc"}
_STAT_LABEL = {"hp": "Health", "at": "Attack", "etc": "Toughness"}


def stat_tier(kind: str, row: int) -> int:
    """0 Low Rank .. 3 hardest G Rank, 4 Nightmare; -1 if unknown. kind: hp, at or etc."""
    kind = _STAT_KEY.get(kind, kind)
    lim = TIERS.get(kind)
    if not lim:
        return -1
    for i, k in enumerate(("LR", "HR", "G")):
        if row < lim[k]:
            return i
    return 3 if row <= lim["MAX"] else NIGHTMARE


def tier_name(tier: int) -> str:
    return TIER_NAMES[tier] if 0 <= tier < len(TIER_NAMES) else ""


def tier_note(kind: str, row: int) -> str:
    """'High Rank' / 'NIGHTMARE: harder than ...' for one stat row."""
    kind = _STAT_KEY.get(kind, kind)
    t = stat_tier(kind, row)
    if t == NIGHTMARE:
        return (f"NIGHTMARE: {_STAT_LABEL[kind].lower()} row {row} is above the hardest row any quest of "
                f"the game uses ({TIERS[kind]['MAX']})")
    return tier_name(t)


def monster_tier(m: dict) -> int:
    """Hardest of the three stats of a monster slot (dict with Nando_hp / Nando_at / Nando_etc)."""
    return max(stat_tier("hp", m["Nando_hp"]), stat_tier("at", m["Nando_at"]),
               stat_tier("etc", m["Nando_etc"]))


def quest_tier(q) -> int:
    tiers = [monster_tier(m) for m in q.monsters if m["Type"]]
    return max(tiers) if tiers else -1


def tier_table(kinds=("hp", "at", "etc")) -> str:
    if not TIERS:
        return ""
    lines = ["Rank label of a row (measured on the game's own monsters; a row below the first limit "
             "is Low Rank, and so on):"]
    for kind in kinds:
        t = TIERS[kind]
        lines.append(f"{_STAT_LABEL[kind]}:  Low Rank below {t['LR']}  ·  High Rank below {t['HR']}  ·  "
                     f"G Rank below {t['G']}  ·  hardest G Rank up to {t['MAX']}  ·  Nightmare above {t['MAX']}")
    return "\n".join(lines)


def table(kind: str) -> str:
    label = {"hp": "Health", "atk": "Attack", "dmg": "Damage taken"}[kind]
    lines = []
    for hub in ("Village", "Port"):
        row = [f"{k.split()[1]}★ ×{GROUPS[k][kind]:g}" for k in group_keys() if k.startswith(hub)]
        if row:
            lines.append(f"{hub}:  " + "   ".join(row))
    if not lines:
        return ""
    return (f"{label} multiplier of the game's own quests (median per star rank):\n"
            + "\n".join(lines) + "\nPort 1-2★ = Low Rank, 3-5★ = High Rank, 6-8★ = G Rank.")


def money_hint(field: str, star: int) -> str:
    keys = [k for k in group_keys() if k.endswith(f" {star}")]
    names = {"contract": ("fee", "fee_range"), "reward_money": ("reward", "reward_range"),
             "main_hrp": ("hrp", "hrp_range")}
    if field not in names or not keys:
        return ""
    k, rng = names[field]
    parts = []
    for key in keys:
        g = GROUPS[key]
        parts.append(f"{group_label(key)}: usually {g[k]:,} (from {g[rng][0]:,} to {g[rng][1]:,})")
    return f"Game quests with {star}★:\n" + "\n".join(parts)


def by_class(field: str, top: int = 3) -> str:
    """Most common values per quest group ('Village: 0 · Port Low Rank: 1 ...')."""
    data = PER_CLASS.get(field)
    if not data:
        return ""
    parts = []
    for cls, vals in data.items():
        if cls == "Tutorial":
            continue
        txt = ", ".join(f"{v}" + (f" ({n}×)" if len(vals) > 1 else "") for v, n in vals[:top])
        parts.append(f"{CLASS_LABEL.get(cls, cls)}: {txt}")
    return "Values in the game's quests:\n" + "\n".join(parts)


_QS = ("mh3u-quest-studio (read in the game's code and checked in the game on the Wii U "
       "version, whose quest data is the same)")


def common(field: str) -> str:
    vals = COMMON.get(field)
    if not vals:
        return ""
    return f"Values used by the game's {N_BASE} quests: " + ", ".join(
        f"{v} ({n}×)" for v, n in vals) + "."


def special_examples() -> str:
    if not EXAMPLES:
        return ""
    lines = [f"{k.replace('/', ' + ')}:  {', '.join(v)}" for k, v in list(EXAMPLES.items())[:9]]
    return "Flag + condition pairs used by the game, with example quests:\n" + "\n".join(lines)


# ------------------------------------------------------------------- texts
TIME_TIP = ("Time limit in minutes. The game's quests use 50 minutes (348 quests) or 30 minutes (16 quests, "
            "mostly arena and special fights).\n\n"
            "Tested in the game: up to 98 minutes the clock counts down normally (51 and 98 were tried); "
            "from 99 minutes it is FROZEN, so the quest never times out (99 and 120 were tried). "
            "Values between 99 and 120 are expected to behave the same; 135 is reported by players to "
            "freeze it too but is untested, and how high a value the game can take is not known. "
            "The 'Frozen clock' box sets 99, the lowest frozen value.")

# (label, Size %, Sizeparam or None = leave as it is)
SIZE_PRESETS = [("Tiny (20 %)", 20, 0), ("Small (40 %)", 40, 0), ("Normal (100 %)", 100, None),
                ("King Size (125 %)", 125, 0), ("Giant (200 %)", 200, 0)]

SIZE_TIP = ("Sets the monster's size in one click. No hidden 'enraged' or 'charged' setting was found in the "
            "quest file: the game's 'Clashing Fists!' Brachydios (124 %) and 'Descent into Hades' Stygian "
            "Zinogre (125 %) are King Size, which the wiki describes as 'always King Size, with increased "
            "health and attack'. So King Size plus higher Health and Attack is the closest the quest can get; "
            "whether such a monster starts the fight enraged or charged is not something this editor can set.\n\n"
            "Sizes seen in the game's quests: 100 (almost everywhere), 121 to 125 (King Size), 20, 40 and 88 "
            "(small), 180 and 200 (giant). Everything except Normal also sets 'Size spread' to 0, as those "
            "quests do, so the size is fixed.")

ARRIVAL_TIP = ("When the large monsters of the quest arrive, and which of them you have to slay to win. The "
               "game's own quests with 2 to 4 large monsters use exactly these patterns; the monsters are "
               "taken in the order of their cards (use ◀ ▶ on a card to reorder them).\n\n"
               "The quest is won when the monsters of the LAST group are slain; the earlier groups have "
               "to be dealt with first, because the next group is brought in after them (assumed from the game's quests, not confirmed).")

ARRIVAL_NOTE = ("The game's own quests with these patterns bring the next group after the previous one. What "
                "exactly triggers it (the previous monsters being slain or captured) is assumed, not "
                "confirmed: please watch it in your first test. The editor writes the objectives itself so "
                "that they match (the targets are the last group). If you change the objectives by hand, a "
                "monster that is not a target stays optional: the quest ends without it.")

SPAWN_TIP = ("The small monsters that live in the zone. Each line is a species and the number of places where "
             "it can appear: the game keeps such a list in every quest, and the game's quests have 5 to 15 "
             "species on a map. Places are copied from the game's own quests on the same map, so they always "
             "suit the map. Replacing a species keeps its places.")

SPAWN_FILL_TIP = ("Copies the complete small-monster list of one of the game's quests on this map (you "
                  "choose which, closest rank first) and sets their strength for the chosen rank. "
                  "Everything stays editable.")

ENV_TIP = ("Stable: only the monsters you listed are in the zone. Unstable: other large monsters can also wander "
           "into the zone at random (the quest board shows 'Environment: Unstable'). You cannot choose WHICH "
           "monsters: the game keeps a roaming-monster list for each zone, outside the quest file (it was not "
           "found in the game's files), and the quest only holds the chance, the maximum and a list number. "
           "The editor therefore reuses the settings of a game quest on the same zone. The monsters named on "
           "the wiki for a quest are not necessarily the roaming ones.\n\n"
           "To have a monster present for sure, add it as a large monster (and use the arrival patterns).")

TEXT = {
    "quest_no": "The quest's number. The game identifies quests by it, so two quests can never "
                "share a number. Event quests use 20000-29999 and challenge quests 61000-61999. "
                "New quests get the first free number automatically.",
    "star": "Star rank shown on the quest board. It is only a label: how strong the monsters "
            "are is set in the Monsters tab.",
    "map": "Where the quest takes place. The game lets each large monster start only on some "
           "maps; on another map it simply does not appear (the editor warns you). The Monster "
           "pack page can lift that limit (ROM hack). When you create a quest, copy one that "
           "already uses the same map: the hidden data at the end of a quest (small monsters, "
           "events) depends on the map.",
    "time_min": TIME_TIP,
    "contract": "Fee: zenny paid to accept the quest.",
    "reward_money": "Zenny earned when the quest is completed.",
    "penalty": "Zenny taken from the reward each time a hunter faints. In every quest of the "
               "game it is one third of the reward (rounded up).",
    "main_hrp": "Hunter Rank points earned when the quest is completed.",
    "failure_hrp": "Hunter Rank points given when the quest fails. 330 of the game's 365 "
                   "quests give 15, the others 0.",
    "clr_pattern": "How the two objectives combine: one objective only, both objectives must "
                   "be done, or either objective completes the quest.",
    "objective": "What the hunter must do. Hunt = slay or capture, Capture = capture only, "
                 "Slay = kill only, Deliver = bring an item to the red supply box. "
                 "Target: the monster (or the item to deliver).\n\n"
                 "How it is counted (for hunts):\n"
                 "· The quest's only large monster: a quest with a single large monster.\n"
                 "· A specific monster of the quest: used when the quest has 2 to 4 large monsters; "
                 "the Target names ONE of them. The targets are the monsters of the LAST group to "
                 "arrive (see 'How the monsters arrive' on the Monsters tab); the quest is won as soon "
                 "as the targets are slain, even if another monster that is not a target is still "
                 "alive.\n"
                 "· Copies of it, one after another: N copies of the same monster that arrive in "
                 "succession.\n"
                 "· Small monsters (count): hunt that many small monsters.\n\n"
                 "Normally you do not need to touch these: the Monsters tab sets them for you.",
    "obj_count": "How many. The game's own quests write it like this: 'Hunt 2 Arzuros' (Double Jeopardy), "
                 "'Slay 12 Altaroth' (Bug Hunt), 'Deliver 3 Unique Mushrooms' (Tutorial 1).",
    "species": "The monster. Pick one the game allows on the quest's map (or install the Monster pack).",
    "Num": "How many copies of this monster arrive one after another. The game uses 1 almost "
           "everywhere, and 3 (or 5) in the 'Hunt 3 X in succession' quests, which have a single "
           "monster card. To have several copies together or in waves, add several cards.",
    "Size": "Size in percent: 100 = normal size. The base game uses 100 everywhere except a few "
            "special quests; event quests use 121 to 125 for King Size monsters, and 20, 40, 88, 180 and "
            "200 for tiny or giant ones.\n\nThe quest file keeps the size in one byte, so 255 % is the "
            "most the game allows on its own. In Developer mode you can type up to 2000 %: above 255 the "
            "editor uses a size table that only the Monster pack (code patch) adds, so the pack must be "
            "installed, or the game reads past its own table. Giant monsters are untested in the game: "
            "they may clip through walls or be hard to hit.",
    "Nando_hp": "HEALTH. Not an HP value: a row (0-127) of the game's difficulty table. The "
                "row gives a multiplier applied to the monster's base HP.",
    "Nando_at": "ATTACK. A row (0-127) of the difficulty table; the row gives how hard the "
                "monster's attacks hit.",
    "Nando_etc": "TOUGHNESS. A row (0-127) of the difficulty table; the row gives how much of "
                 "your damage the monster takes (lower = tougher). The same row also sets "
                 "flinch and part-break resistance.",
    "Stamina": "How fast the monster gets tired (stamina table). The game uses: Village 0, "
               "Port Low and High Rank 1, Port G Rank 2, Grudge Matches and Challenge "
               "quests 3.",
    "Sizeparam": "Size spread: which table decides how much smaller or bigger than 'Size %' "
                 "the monster can be (this is what makes crowns possible). The game uses: "
                 "Village 1, 10 or 13; Port Low Rank 1; Port High Rank 3 to 7; Port G Rank "
                 "18 to 28; Grudge Matches and Challenge quests 0 (fixed size). The game's table "
                 "ends at 34; with the Monster pack, 64 to 82 are exact sizes +100 % to +1900 % "
                 "(set by 'Size %' above 255).",
    "Starttype": "Start position number of the monster on the map. 0 = the game's usual start "
                  "(3 large monsters out of 4 in the game). The game keeps, for every monster and "
                  "map, a short list of start areas and this number picks one: Rathian on the "
                  "Deserted Island has 4 (areas 10, 2, 5, 4), Zinogre on Misty Peaks 3. The 'Start "
                  "positions' button shows the area of each number, read from the game's code. A "
                  "number past the end of the list is flagged by the checks.",
    "Settype": "0 in every quest of the game (all 403 quests checked). Leave it at 0.",
    "Nando2": "Second difficulty value (purpose not confirmed). The game uses 0 in most "
              "Village and Port G Rank quests, 1 in most Port Low/High Rank and event quests. "
              "Keep the value of the quest you copied.",
    "rewards": "Each line: an item, how many, and its chance in percent. At the end of the "
               "quest the game draws several times from the table. Table A is the main "
               "reward; table B is drawn separately.",
    "item_set_no": "The supply box at the base camp. Each set is a fixed list of items "
                   "defined by the game; pick the one whose contents fit your quest.",
    "supp_set_no": "TIMED DELIVERY (the game calls it SuppTimeFlag). 0 = the whole box at the start; "
                   "1 = part of the box at the start (by rank), the rest later on a random timer; 2 = "
                   "the first 8 slots at the start, the rest after 2 minutes; 3 = part at the start, the "
                   "rest only from the hunt delivery. Meanings from " + _QS + ". " + common("supp_set_no"),
    "supp_time_flag": "HUNT DELIVERY, monster (the game's SuppEnemyType): the rest of the supplies comes "
                      "once this monster is hunted. 0 = no hunt delivery. Source: " + _QS + ". "
                      + common("supp_time_flag"),
    "supp_enemy_type": "HUNT DELIVERY, count (the game's SuppEnemyNum): how many of that monster must be "
                       "hunted. Source: " + _QS + ". " + common("supp_enemy_type"),
    "supp_enemy_num": "WHERE THE HUNTERS START (the game calls it StartParam). 0 = base camp; 1 = a "
                      "random area on the main hunting maps, with the game's own odds for each map; 2 = a "
                      "fixed area on the Underwater Ruin, Sacred Land and Tainted Sea. Elsewhere 1 and 2 "
                      "change nothing. The odds were read from the game's table (3DS code.bin, the same as "
                      "the Wii U one, where random and fixed starts were confirmed in the game by "
                      "mh3u-quest-studio). " + common("supp_enemy_num"),
    "ren_pattern": "A field the game calls Rannyu_limite: 0 in every quest of the game. Leave it at 0.",
    "start_param": "ARRIVAL PATTERN of the large monsters (the game calls this field Ren_pattern; read in the order of their cards). 0 = "
                   "all at the start; 1 = one after another; 5 = the first, then the other two "
                   "together (3 monsters); 6 = the first two together, then the last one (3 monsters); "
                   "4 = the first, then two together, then the last (4 monsters); 8 = two together, "
                   "then two together (4 monsters). Found by comparing the game's 100 multi-monster "
                   "quests; the Monsters tab sets it for you. " + common("start_param"),
    "main_zako1": "First of the two 'main' small-monster species (always one of the species of the "
                  "quest's small-monster list). Developer mode only: the list on the Monsters tab "
                  "keeps these in step.",
    "main_zako2": "Second of the two 'main' small-monster species.",
    "nora_set_type": "1 when the quest uses a roaming-monster list, 0 otherwise.",
    "nora_set_per": "Chance in percent that roaming (stray) large monsters show up. 0 = the "
                    "environment is Stable; above 0 it is Unstable (checked on 250 game quests).",
    "nora_per_type": "A second percentage next to the chance (10, 20, 30, 50, 80 or 100 in the game's "
                     "quests). Purpose not confirmed.",
    "nora_set_max": "Most roaming monsters at the same time (1 or 2).",
    "nora_set_table": "Number of the roaming-monster list of the map. The lists live in the game, "
                      "so only numbers that a game quest on the same map uses are safe.",
    "nora_pekko": "1 in a few quests whose roaming monster always comes (100 % / 100 %).",
    "zako_rows": "Strength of the small monsters: rows of the same difficulty table as the "
                 "large monsters (health / attack / toughness).",
    "hagi_no": "Two values in one number. Low byte: the supply rank (the game's HagiNo): 0 = low rank, "
               "no timed delivery; 1 = high rank; 2 = G rank; 3 = arena, the whole box and no "
               "deliveries; 4 = multi-monster hunts. High byte: the story step (ProgNo), 0 except in a few "
               "quests. Source: " + _QS + ". " + common("hagi_no"),
    "prog_no": "MONSTER RANK (the game calls it EnemyLv): 0 = low rank (Village), 1 = low rank (Port), "
               "2 = high rank (Village), 3 = high rank (Port), 4 = G rank. It does not change the monsters' "
               "health (that is the Health row). Source: " + _QS + ".",
    "enemy_lv": "INTRO CUTSCENE (the game calls it DemoNo): 0 = none; the other values play the opening "
                "cutscene of a story quest. " + common("enemy_lv"),
    "demo_no": "Low byte of a field the game does not use (ItemSetNo): 0 in every quest. Leave it at 0.",
    "special_flag": "Special quest behaviour (arena fights, Harvest Tours, final battles...). "
                    "Meaning of each value not confirmed: keep the value of the quest you "
                    "copied.\n\n" + special_examples(),
    "special_cond": "Goes with the special flag above.",
    "special_cond2": "Second special condition. " + common("special_cond2"),
    "category": "Quest category bits. Bits 4 and 20 together cut monster HP to 55% (used by "
                "Grudge Matches and challenge quests). Other bits are only known by which "
                "quests use them.",
    "dev_mode": "Developer mode shows internal numbers (ids, type codes, raw fields) and the "
                "Advanced tab. Keep it off for normal editing.",
    "zako_ptr": "Internal pointer value; keep as is.",
    "challenge": "Pack 4 holds the game's Challenge quests (61000+). A quest placed there shows "
                 "up in the Challenge quest list, not with the event quests. Use packs 1-3 for "
                 "custom event quests.",
}


def tip(key: str) -> str:
    return TEXT.get(key, "")


def stat_tip(field: str) -> str:
    kind = {"Nando_hp": "hp", "Nando_at": "atk", "Nando_etc": "dmg"}[field]
    return (TEXT[field] + "\n\n" + table(kind) + "\n\n"
            + tier_table((_STAT_KEY[field],)) + "\nAbove the last limit the label is Nightmare: "
            "harder than any quest of the game.")


def describe_stats(em: int, hp: int, at: int, df: int, category: int = 0) -> dict:
    """Readable values for a monster's three difficulty rows."""
    s = G.monster_stats(em, hp, at, df, category)
    if s is None:
        return {}
    return {
        "hp": f"HP ×{s.hp_mult:g}" + (f" = {s.est_hp:,} HP" if s.est_hp else "")
              + (" (×0.55 cut)" if s.hp_cut else ""),
        "atk": f"attacks ×{s.atk_mult:g}",
        "dmg": f"takes ×{s.dmg_mult:g} damage",
        "hp_like": nearest("hp", s.hp_mult), "atk_like": nearest("atk", s.atk_mult),
        "dmg_like": nearest("dmg", s.dmg_mult),
        "hp_tier": tier_note("hp", hp), "atk_tier": tier_note("at", at), "dmg_tier": tier_note("etc", df),
        "hp_t": stat_tier("hp", hp), "atk_t": stat_tier("at", at), "dmg_t": stat_tier("etc", df),
        "hp_mult": s.hp_mult, "atk_mult": s.atk_mult, "dmg_mult": s.dmg_mult,
    }
