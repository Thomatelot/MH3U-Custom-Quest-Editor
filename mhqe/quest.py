"""MH3U quest record ('QTDS', little-endian): parser and in-place editor.

The same record format is used by

* the base-game quests (``quest/eu/q_NNNNN.quest`` and ``quest00.arc``), and
* the downloadable event / challenge quests stored in the ``quest1``..``quest4``
  packs of the game's extdata.

Field layout and names come from the community research published in
Matt-Wood-23/mh3u-quest-studio (MIT licence, see THIRD_PARTY.md) and were
re-verified against the 3DS (EU) files this editor targets: every field is
recorded with its byte offset, so a record can be edited in place and written
back byte-for-byte identical when nothing changed.

Anything that is not understood (the tail of the record, unknown scalars) is
kept verbatim and written back untouched.
"""
from __future__ import annotations

import struct

MAGIC = b"QTDS"
NLANG = 5
LANGS = ("en", "fr", "de", "it", "es")
LANG_NAMES = {"en": "English", "fr": "French", "de": "German",
              "it": "Italian", "es": "Spanish"}

STRING_FIELDS = ("name", "objective", "sub_objective", "failure",
                 "client", "description")

MON_FIELDS = ("Type", "Settype", "Starttype", "Num", "Nando_hp", "Nando_at",
              "Nando_etc", "Nando2", "Size", "Sizeparam", "Stamina")
MON_SLOTS = 5
MON_SIZE = len(MON_FIELDS)
NANDO_FIELDS = ("Nando_hp", "Nando_at", "Nando_etc")
NANDO_MAX = 127

REWARD_SLOTS = 32
REWARD_REGION = REWARD_SLOTS * 4 * 2          # Reward1 + Reward2, 4 bytes/slot
MIN_AFTER_REWARDS = 94                        # fixed cluster that must follow

CLR_PATTERNS = {0: "Single objective", 1: "Objective A and B",
                2: "Objective A or B"}

# Low u16 of an objective's "param" word.
OBJ_TYPES = {
    0x0000: "(none)",
    0x0001: "Hunt",
    0x0002: "Deliver",
    0x0081: "Capture",
    0x0101: "Slay",
    0x8101: "Slay small monster",
    0x0404: "Repel (siege)",
    0x2515: "Repel siege (Jhen Mohran)",
    0x4014: "Repel siege (Ceadeus)",
    0x2000: "Siege damage",
}
OBJ_MONSTER_TYPES = (0x0001, 0x0081, 0x0101, 0x8101, 0x0404, 0x2515, 0x4014)
OBJ_ITEM_TYPES = (0x0002,)


class QuestFormatError(ValueError):
    """The bytes are not a valid / supported MH3U quest record."""


class Quest:
    """One quest record. Edit with the setters; read the bytes with to_bytes()."""

    # ------------------------------------------------------------ construction
    def __init__(self, data: bytes | bytearray):
        self.data = bytearray(data)
        self._parse()

    @classmethod
    def from_bytes(cls, data: bytes | bytearray) -> "Quest":
        return cls(data)

    def copy(self) -> "Quest":
        return Quest(bytes(self.data))

    def to_bytes(self) -> bytes:
        return bytes(self.data)

    def replace_bytes(self, data: bytes | bytearray) -> None:
        """Load other bytes into this same object (used by 'Undo changes')."""
        old = self.data
        self.data = bytearray(data)
        try:
            self._parse()
        except QuestFormatError:
            self.data = old
            self._parse()
            raise

    # ------------------------------------------------------------------ parse
    def _parse(self) -> None:
        d = self.data
        if bytes(d[:4]) != MAGIC:
            raise QuestFormatError(f"not a quest record (magic {bytes(d[:4])!r})")
        self._scalar: dict[str, tuple[int, str]] = {}   # name -> (offset, fmt)
        self._order: list[str] = []                     # scalar names in file order
        self._str_off: dict[str, list[int]] = {}        # field -> [len-prefix offsets]
        self._texts: dict[str, list[bytes]] = {}
        pos = 4

        def need(n: int) -> None:
            if pos + n > len(d):
                raise QuestFormatError("record is truncated")

        def u(fmt: str):
            nonlocal pos
            n = struct.calcsize(fmt)
            need(n)
            (v,) = struct.unpack_from(fmt, d, pos)
            pos += n
            return v

        def scalar(name: str, fmt: str) -> None:
            nonlocal pos
            self._scalar[name] = (pos, fmt)
            self._order.append(name)
            u(fmt)

        def strs(name: str) -> None:
            nonlocal pos
            offs, vals = [], []
            for _ in range(NLANG):
                offs.append(pos)
                n = u("<I")
                need(n)
                vals.append(bytes(d[pos:pos + n]))
                pos += n
            self._str_off[name] = offs
            self._texts[name] = vals

        if u("<I") != NLANG:
            raise QuestFormatError("unexpected language count")
        strs("name")
        scalar("quest_no", "<H")
        strs("objective")
        scalar("star", "B")
        scalar("map", "B")
        strs("sub_objective")
        scalar("time_min", "<H")
        strs("failure")
        scalar("special_flag", "<H")
        scalar("special_cond", "<H")
        scalar("special_cond2", "<H")
        strs("client")
        strs("description")
        scalar("main_zako1", "B")
        scalar("main_zako2", "B")
        scalar("category", "<Q")

        self._mon_off: list[int] = []
        for _ in range(MON_SLOTS):
            need(MON_SIZE)
            self._mon_off.append(pos)
            pos += MON_SIZE

        for name in ("nora_set_per", "nora_per_type", "nora_set_type",
                     "nora_set_max", "nora_set_table", "nora_pekko"):
            scalar(name, "B")

        self._rewards_start = pos
        if pos + REWARD_REGION + MIN_AFTER_REWARDS > len(d):
            raise QuestFormatError("record too short for the reward section")
        pos += REWARD_REGION

        scalar("contract", "<i")          # fee
        scalar("reward_money", "<i")
        scalar("penalty", "<i")           # == ceil(reward / 3) in every game quest
        scalar("main_hrp", "<i")
        scalar("failure_hrp", "<i")
        # Field names below are the editor's historical names. The game's reader (as found by
        # mh3u-quest-studio, field by field, and checked against the 3DS quests) names them:
        #   hagi_no (u16)  = HagiNo (u8, supply rank) + ProgNo (u8, story step)
        #   prog_no = EnemyLv (monster rank)     enemy_lv = DemoNo (intro cutscene)
        #   demo_no + pad  = ItemSetNo (u16, 0)   item_set_no = SuppSetNo (supply box)
        #   supp_set_no = SuppTimeFlag   supp_time_flag = SuppEnemyType   supp_enemy_type = SuppEnemyNum
        #   supp_enemy_num = StartParam (where the hunters start)
        #   start_param = Ren_pattern (monster arrival pattern)   ren_pattern = Rannyu_limite (0)
        # The names are kept so that existing files, tables and settings stay valid.
        scalar("hagi_no", "<H")
        scalar("prog_no", "B")
        scalar("enemy_lv", "B")
        scalar("demo_no", "B")
        need(1)
        pos += 1                          # padding byte
        scalar("item_set_no", "<H")       # selects suppNNN.supp (supply crate)
        scalar("supp_set_no", "<H")
        scalar("supp_time_flag", "<H")
        scalar("supp_enemy_type", "<H")
        scalar("supp_enemy_num", "<H")
        scalar("start_param", "<H")
        scalar("ren_pattern", "<H")
        scalar("zako_ptr", "<I")
        scalar("zako_nando_hp", "<I")
        scalar("zako_nando_at", "<I")
        scalar("zako_nando_etc", "<I")
        scalar("zako_param1", "<H")
        scalar("zako_id1", "<H")
        scalar("zako_num1", "<H")
        scalar("zako_param2", "<H")
        scalar("zako_id2", "<H")
        scalar("zako_num2", "<H")
        scalar("enemybox_type", "<I")
        scalar("unk_m72", "<I")
        scalar("clr_pattern", "<H")
        scalar("obj1_param", "<I")
        scalar("obj1_id", "<H")
        scalar("obj1_num", "<h")
        scalar("obj2_param", "<I")
        scalar("obj2_id", "<H")
        scalar("obj2_num", "<h")
        self._rest_off = pos

    # ----------------------------------------------------------------- scalars
    @property
    def scalar_names(self) -> list[str]:
        return list(self._order)

    def scalar_format(self, name: str) -> str:
        return self._scalar[name][1]

    def scalar_range(self, name: str) -> tuple[int, int]:
        fmt = self._scalar[name][1]
        size = struct.calcsize(fmt)
        if fmt[-1].isupper() or fmt == "B":
            return 0, (1 << (8 * size)) - 1
        return -(1 << (8 * size - 1)), (1 << (8 * size - 1)) - 1

    def get(self, name: str) -> int:
        off, fmt = self._scalar[name]
        return struct.unpack_from(fmt, self.data, off)[0]

    def set(self, name: str, value: int) -> None:
        off, fmt = self._scalar[name]
        lo, hi = self.scalar_range(name)
        value = int(value)
        if not lo <= value <= hi:
            raise QuestFormatError(f"{name} must be between {lo} and {hi}")
        struct.pack_into(fmt, self.data, off, value)

    # ----------------------------------------------------------------- strings
    def get_text(self, field: str, lang: int = 0) -> str:
        return self._texts[field][lang].decode("utf-8", "replace")

    def get_raw_text(self, field: str, lang: int = 0) -> bytes:
        return self._texts[field][lang]

    def set_text(self, field: str, text: str | bytes, langs=range(NLANG)) -> None:
        """Replace a text in the given language slots (record length changes)."""
        enc = text if isinstance(text, bytes) else text.encode("utf-8")
        new = struct.pack("<I", len(enc)) + enc
        for lang in sorted(set(langs), reverse=True):   # back-to-front keeps offsets valid
            off = self._str_off[field][lang]
            old_len = struct.unpack_from("<I", self.data, off)[0]
            self.data[off:off + 4 + old_len] = new
        self._parse()

    # ---------------------------------------------------------------- monsters
    @property
    def monsters(self) -> list[dict[str, int]]:
        out = []
        for off in self._mon_off:
            out.append(dict(zip(MON_FIELDS, self.data[off:off + MON_SIZE])))
        return out

    def set_monster(self, slot: int, **fields: int) -> None:
        off = self._mon_off[slot]
        for key, value in fields.items():
            if key not in MON_FIELDS:
                raise QuestFormatError(f"unknown monster field {key!r}")
            value = int(value)
            if not 0 <= value <= 255:
                raise QuestFormatError(f"{key} must be between 0 and 255")
            self.data[off + MON_FIELDS.index(key)] = value

    def clear_monster(self, slot: int) -> None:
        off = self._mon_off[slot]
        self.data[off:off + MON_SIZE] = bytes(MON_SIZE)

    def set_monster_all(self, slot: int, values: dict[str, int]) -> None:
        self.set_monster(slot, **{k: values[k] for k in MON_FIELDS})

    # ----------------------------------------------------------------- rewards
    def _read_rewards(self, table: int) -> list[tuple[int, int, int]]:
        start = self._rewards_start + (table - 1) * REWARD_SLOTS * 4
        recs = []
        for i in range(REWARD_SLOTS):
            iid, num, per = struct.unpack_from("<HBB", self.data, start + i * 4)
            if iid == 0 or (iid == 5 and num == 0 and per == 0):
                break
            recs.append((iid, num, per))
        return recs

    @property
    def reward1(self) -> list[tuple[int, int, int]]:
        return self._read_rewards(1)

    @property
    def reward2(self) -> list[tuple[int, int, int]]:
        return self._read_rewards(2)

    def set_reward_table(self, table: int, records) -> None:
        """Write (item_id, quantity, chance%) rows. The list ends at the first
        item id 0, so the slot after the last row is cleared."""
        if table not in (1, 2):
            raise QuestFormatError("reward table must be 1 or 2")
        records = [(int(i), int(n), int(p)) for i, n, p in records]
        if len(records) > REWARD_SLOTS:
            raise QuestFormatError(f"at most {REWARD_SLOTS} rewards per table")
        for iid, num, per in records:
            if not (1 <= iid <= 0xFFFF and 0 <= num <= 255 and 0 <= per <= 255):
                raise QuestFormatError("reward values out of range")
        start = self._rewards_start + (table - 1) * REWARD_SLOTS * 4
        old = len(self._read_rewards(table))
        for i, (iid, num, per) in enumerate(records):
            struct.pack_into("<HBB", self.data, start + i * 4, iid, num, per)
        if len(records) != old:
            # zero removed rows and the terminator slot after the new list;
            # untouched bytes past an unchanged list are left exactly as found
            clear_to = min(max(old, len(records) + 1), REWARD_SLOTS)
            for i in range(len(records), clear_to):
                struct.pack_into("<HBB", self.data, start + i * 4, 0, 0, 0)

    # -------------------------------------------------------------- objectives
    def objective(self, which: int) -> tuple[int, int, int, int]:
        """(type, param_high, target_id, count) for objective 1 or 2."""
        param = self.get(f"obj{which}_param")
        return (param & 0xFFFF, param >> 16,
                self.get(f"obj{which}_id"), self.get(f"obj{which}_num"))

    def set_objective(self, which: int, obj_type: int, target_id: int,
                      count: int, param_high: int | None = None) -> None:
        if param_high is None:
            param_high = self.get(f"obj{which}_param") >> 16
        self.set(f"obj{which}_param", ((param_high & 0xFFFF) << 16) | (obj_type & 0xFFFF))
        self.set(f"obj{which}_id", target_id)
        self.set(f"obj{which}_num", count)

    # --------------------------------------------------------------- misc info
    @property
    def tail(self) -> bytes:
        """Everything after the parsed fields (event-trigger data, padding)."""
        return bytes(self.data[self._rest_off:])

    def pad_to(self, size: int) -> None:
        """Zero-pad the record to *size* bytes (the base-game quest files are shorter than an event slot)."""
        if len(self.data) < size:
            self.data.extend(bytes(size - len(self.data)))

    def set_tail(self, tail: bytes) -> None:
        """Replace everything after the parsed fields, keeping the record length (zero padding
        is added or trimmed; anything else that does not fit is an error)."""
        tail = bytes(tail)
        size = len(self.data) - self._rest_off
        if len(tail) > size:
            if any(tail[size:]):
                raise QuestFormatError(
                    f"the quest data is {len(tail.rstrip(bytes(1))) - size} bytes too long to fit")
            tail = tail[:size]
        else:
            tail = tail + bytes(size - len(tail))
        self.data[self._rest_off:] = tail

    @property
    def used_length(self) -> int:
        """Record length without trailing zero padding."""
        return len(bytes(self.data).rstrip(b"\0"))

    def summary(self) -> str:
        mons = ", ".join(f"em{m['Type']:03d}x{m['Num']}"
                         for m in self.monsters if m["Type"])
        return (f"#{self.get('quest_no'):05d} {self.get('star')}* "
                f"map{self.get('map')} {self.get('time_min')}min "
                f"[{mons or 'no large monster'}] {self.get_text('name')!r}")


def identity_rewrite(data: bytes) -> bytes:
    """Self-test helper: write every field back with its own value."""
    q = Quest(data)
    for name in q.scalar_names:
        q.set(name, q.get(name))
    for slot, mon in enumerate(q.monsters):
        q.set_monster(slot, **mon)
    q.set_reward_table(1, q.reward1)
    q.set_reward_table(2, q.reward2)
    for field in STRING_FIELDS:
        for lang in range(NLANG):
            q.set_text(field, q.get_raw_text(field, lang), langs=[lang])
    return q.to_bytes()
