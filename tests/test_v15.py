"""Tests for version 1.5: game code tables, progression, roaming lists, arena rules, new base-game
quests. Need MHQE_ROMFS (romfs folder of the game, with exefs/code.bin next to it)."""
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mhqe import arc as arcmod, gamecode as GC, monsterpack as MP, progress, rules, startpos, strays  # noqa: E402
from mhqe.project import RomSource  # noqa: E402

ROMFS = os.environ.get("MHQE_ROMFS")


def _apply_ips(code: bytes, ips: bytes) -> bytes:
    out, i = bytearray(code), 5
    while ips[i:i + 3] != b"EOF":
        off, n = int.from_bytes(ips[i:i + 3], "big"), int.from_bytes(ips[i + 3:i + 5], "big")
        i += 5
        if n == 0:
            n = int.from_bytes(ips[i:i + 2], "big")
            out[off:off + n] = ips[i + 2:i + 3] * n
            i += 3
        else:
            out[off:off + n] = ips[i:i + n]
            i += n
    return bytes(out)


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class GameCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = MP.GameFiles(ROMFS)
        cls.rom = RomSource(ROMFS, workspace=Path(tempfile.mkdtemp()), load_edits=False)

    def test_tables_match_the_shipped_data(self):
        code = self.game.code
        _off, lst = GC.find_master_list(code)
        self.assertEqual(len(lst), 504)
        self.assertIn(12801, lst)
        self.assertEqual(GC.roaming_tables(code), strays.game_tables())
        self.assertEqual(startpos.form(72, 5, 1), 3)          # Stygian Zinogre, Volcano, start 1
        self.assertEqual(startpos.form(74, 5, 1), 1)          # Brachydios, Volcano, start 1
        self.assertEqual(startpos.form(1, 1, 0), 0)

    def test_key_quests_as_the_game(self):
        quests = self.rom.quests
        self.assertEqual(progress.keys_of(quests, 12201), [11105, 11109, 11110, 11112])
        self.assertIn(11715, progress.keys_of(quests, 12801))
        self.assertEqual(progress.key_for(quests, 11105), [12201])
        for no in quests:                                     # the game's quests have no progression error
            self.assertFalse([p for p in progress.problems(quests, no) if p[0] == "error"], no)

    def test_new_key_quest_and_export(self):
        rom = RomSource(ROMFS, workspace=Path(tempfile.mkdtemp()), load_edits=False)
        q = rom.create(11120, rom.quests[11105])
        progress.write(q, 0, 0, 0)
        before = progress.read(rom.quests[12201])[2]
        changed = progress.set_key(rom.quests, 11120, 12201)
        self.assertEqual(set(changed), {11120, 12201})
        self.assertEqual(progress.read(rom.quests[12201])[2], before + 1)
        self.assertIn(11120, progress.keys_of(rom.quests, 12201))
        self.assertTrue(any(lv == "error" for lv, _t in progress.problems(rom.quests, 11120)))   # not registered
        self.assertFalse(progress.problems(rom.quests, 11120, {"quests": {"11120": 353}}))
        progress.set_key(rom.quests, 11120, None)
        self.assertEqual(progress.read(rom.quests[12201])[2], before)
        out = Path(tempfile.mkdtemp())
        rom.export_mod(out)
        arc = arcmod.read(out / "arc" / "quest" / rom.region_dir / "quest00.arc")
        self.assertEqual(len(arc.entries), len(rom._arc.entries) + 1)
        self.assertTrue(any(e.leaf == "q_11120" for e in arc.entries))

    def test_pack_extras(self):
        like = strays.game_tables()[187][0]
        free = strays.free_slots()[0]
        extras = {"quests": [11120], "roaming": {free: [strays.make_entry(41, 100, like)]}}
        out = Path(tempfile.mkdtemp()) / "pack"
        man = MP.build(ROMFS, out, log=lambda *_a: None, extras=extras)
        self.assertTrue(MP.is_current(man) and MP.extras_match(man, extras))
        self.assertTrue(any(p["em"] == 25 for p in man["added"]))        # Jhen Mohran is placed elsewhere
        code = _apply_ips(self.game.code, (out / "exefs" / "code.ips").read_bytes())
        _off, lst = GC.find_master_list(code)
        self.assertIn(11120, lst)
        self.assertEqual(GC.roaming_tables(code)[free][0][0], 41)


class Rules(unittest.TestCase):
    def test_arena_line_and_carves(self):
        req = rules.Req(6, 4, False)
        self.assertEqual(rules.flag_for(req, 13, arena=True), 16)        # 'HR 6 ... Max participants: 4'
        self.assertEqual(rules.flag_for(req, 13), 6)

        class Q:
            def __init__(self):
                self.v = {"category": 0x28010011, "quest_no": 60002}

            def get(self, k):
                return self.v[k]

            def set(self, k, x):
                self.v[k] = x
        q = Q()
        self.assertEqual(rules.carves(q), "arena")
        rules.set_carves(q, False)
        self.assertEqual(q.v["category"], 0x00010011)
        self.assertEqual(rules.carves(q), "normal")
        self.assertTrue(rules.is_arena(q))
