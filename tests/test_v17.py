"""Tests for version 1.7: monster categories, small-monster places, starts of your own, the
experimental hub map. The pack tests need MHQE_ROMFS (romfs folder with exefs/code.bin next to it
and the monster archives in romfs/arc/enemy)."""
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mhqe import catalog, gamecode as GC, gamedata as G, monsterpack as MP, spawns, startpos  # noqa: E402
sys.path.insert(0, os.path.dirname(__file__))
from test_v15 import _apply_ips  # noqa: E402

ROMFS = os.environ.get("MHQE_ROMFS")


class Categories(unittest.TestCase):
    def test_volvidon_is_a_fanged_beast(self):
        self.assertEqual(catalog.MONSTER_CLASS[44], "Fanged Beasts")
        self.assertEqual(catalog.MONSTER_CLASS[42], "Fanged Beasts")
        self.assertEqual(catalog.MONSTER_CLASS[15], "Leviathans")


class Places(unittest.TestCase):
    def test_record_fields(self):
        raw = bytearray(45)
        struct.pack_into("<II", raw, 0, 34, 255)
        raw[14], raw[15], raw[16] = 3, 2, 1
        struct.pack_into("<6f", raw, 21, 1.0, 2.0, 3.0, 0.0, 16384.0, 0.0)
        p = spawns.Place(bytes(raw))
        self.assertEqual((p.em, p.respawn, p.area, p.count, p.variant), (34, 255, 3, 2, 1))
        self.assertEqual(p.pos, (1.0, 2.0, 3.0, 16384.0))
        p.area, p.count, p.pos = 5, 4, (7, 8, 9, 0)
        q = spawns.Place(bytes(p))
        self.assertEqual((q.area, q.count, q.pos[:3]), (5, 4, (7.0, 8.0, 9.0)))

    def test_hub_map_names(self):
        try:
            G.set_map9("village")
            self.assertIn("Moga Village", G.map_name(9))
            self.assertEqual(G.MAP_TO_INTERNAL[9], 8)
            self.assertEqual(sorted(G.hub_areas(9)), [0, 1, 2])
            self.assertIsNone(G.hub_areas(8))
            G.set_map9("port")
            self.assertEqual(sorted(G.hub_areas(9)), [0, 1])
        finally:
            G.set_map9("")
        self.assertIsNone(G.MAP_TO_INTERNAL[9])
        self.assertIsNone(G.hub_areas(9))


class OwnStarts(unittest.TestCase):
    PACK = {"added": [{"em": 41, "stage": 2, "donor": 56, "start_areas": [3, 8, 1]}],
            "starts": [{"em": 74, "map": 1, "stage": 1, "area": 9, "form": 1, "flag": None, "index": 1}]}

    def tearDown(self):
        startpos.CUSTOM.clear()

    def test_numbers_come_after_the_games(self):
        startpos.CUSTOM[:] = [{"em": 74, "map": 1, "area": 9, "form": 1, "flag": None},
                              {"em": 74, "map": 1, "area": 3, "form": 0, "flag": 1},
                              {"em": 41, "map": 2, "area": 3, "form": 0, "flag": None}]
        self.assertEqual(startpos.planned_number(0, self.PACK), 1)
        self.assertEqual(startpos.planned_number(1, self.PACK), 2)
        self.assertEqual(startpos.planned_number(2, self.PACK), 3)

    def test_built_starts_show_in_the_list(self):
        ar = startpos.areas(74, 1, self.PACK)
        self.assertEqual(ar, [5, 9])
        self.assertIsNotNone(startpos.own_start(74, 1, 1, self.PACK))
        self.assertEqual(startpos.form(74, 1, 1, self.PACK), 1)
        self.assertIn("your start", startpos.choice_text(1, ar, 1, 74, self.PACK))

    def test_problems(self):
        self.assertTrue(startpos.custom_problems({"em": 1, "map": 1, "area": 10, "form": 2}))
        self.assertFalse(startpos.custom_problems({"em": 72, "map": 5, "area": 5, "form": 3}))
        self.assertTrue(startpos.custom_problems({"em": 74, "map": 1, "area": 2, "form": 0}))

    def test_extras_match(self):
        man = {"quests": {}, "roaming": {}, "starts": [{"em": 74, "map": 1, "area": 9, "form": 1, "flag": None}],
               "map9": "village"}
        self.assertTrue(MP.extras_match(man, {"starts": [{"em": 74, "map": 1, "area": 9, "form": 1}],
                                              "map9": "village"}))
        self.assertFalse(MP.extras_match(man, {"starts": [], "map9": "village"}))
        self.assertFalse(MP.extras_match(man, {"starts": man["starts"], "map9": ""}))


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class PackBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = MP.GameFiles(ROMFS)
        cls.tmp = Path(tempfile.mkdtemp())
        cls.base = MP.build(ROMFS, cls.tmp / "base", log=lambda s: None)
        cls.code0 = _apply_ips(cls.game.code, (cls.tmp / "base" / "exefs" / "code.ips").read_bytes())
        cls.table = MP.find_placement_table(cls.game.code, cls.game.layout)

    def _lists(self, code):
        out = {}
        for em in range(86):
            p = struct.unpack_from("<I", code, self.table - MP.BASE + 4 * em)[0]
            if not p:
                continue
            o, lst = p - MP.BASE, {}
            while True:
                st, q = struct.unpack_from("<II", code, o)
                o += 8
                if st == 0xFF:
                    break
                recs, end = MP._records_at(code, q)
                lst[st] = ([r[4:] for r in recs], end)
            out[em] = lst
        return out

    def test_own_starts_are_appended_and_nothing_else_changes(self):
        starts = [{"em": 74, "map": 1, "area": 9, "form": 1}, {"em": 41, "map": 8, "area": 1, "form": 3},
                  {"em": 5, "map": 6, "area": 2}]
        man = MP.build(ROMFS, self.tmp / "starts", log=lambda s: None, extras={"starts": starts})
        self.assertTrue(MP.extras_match(man, {"starts": starts}))
        code = _apply_ips(self.game.code, (self.tmp / "starts" / "exefs" / "code.ips").read_bytes())
        a, b = self._lists(self.code0), self._lists(code)
        mine = {(x["em"], x["stage"]): x for x in man["starts"]}
        self.assertEqual(len(mine), 3)
        for em in a:
            for st in a[em]:
                ra, rb = a[em][st], b[em][st]
                self.assertEqual(ra[1], rb[1])
                self.assertEqual(rb[0][:len(ra[0])], ra[0], (em, st))
                if (em, st) in mine:
                    x = mine[(em, st)]
                    self.assertEqual(len(rb[0]), len(ra[0]) + 1)
                    self.assertEqual(x["index"], len(ra[0]))
                    self.assertEqual((rb[0][-1][5], rb[0][-1][7]), (x["area"], x["form"]))
                else:
                    self.assertEqual(len(rb[0]), len(ra[0]))

    def test_the_games_own_pointers_still_see_their_start_lists(self):
        """Start lists freed for your starts: no word of the game's code (other than the old placement
        lists the pack replaces) may point to one."""
        man = MP.build(ROMFS, self.tmp / "own", log=lambda s: None,
                       extras={"starts": [{"em": 74, "map": 1, "area": 9, "form": 1}]})
        self.assertTrue(man["starts"])
        code0 = self.game.code
        code = _apply_ips(code0, (self.tmp / "own" / "exefs" / "code.ips").read_bytes())
        place = MP.read_placement(code0, self.table)
        sizes = {}
        for lst in place.values():
            for _st, q in lst:
                recs, _end = MP._records_at(code0, q)
                sizes[q] = 56 * (len(recs) + 1)
        old_entries = set()
        for em in range(86):
            p = struct.unpack_from("<I", code0, self.table - MP.BASE + 4 * em)[0]
            if p:
                o = p - MP.BASE
                while struct.unpack_from("<I", code0, o)[0] != 0xFF:
                    old_entries.add(o + 4)
                    o += 8
        for o in range(0, len(code) - 3, 4):
            v = struct.unpack_from("<I", code, o)[0]
            if v in sizes and code[o:o + 4] == code0[o:o + 4] and o not in old_entries:
                a = v - MP.BASE
                self.assertEqual(code[a:a + sizes[v]], code0[a:a + sizes[v]], hex(o + MP.BASE))

    def test_a_wrong_area_keeps_the_pack_built_before(self):
        out = self.tmp / "keep"
        MP.build(ROMFS, out, log=lambda s: None)
        with self.assertRaises(MP.PackError):
            MP.build(ROMFS, out, log=lambda s: None, extras={"starts": [{"em": 74, "map": 1, "area": 2}]})
        self.assertTrue((out / MP.MANIFEST).is_file())
        self.assertFalse(out.with_name(out.name + ".building").exists())

    def test_hub_map_changes_three_bytes(self):
        man = MP.build(ROMFS, self.tmp / "hub", log=lambda s: None, extras={"map9": "port"})
        self.assertEqual(man["map9"], "port")
        code = _apply_ips(self.game.code, (self.tmp / "hub" / "exefs" / "code.ips").read_bytes())
        diff = [i for i in range(len(code)) if code[i] != self.code0[i]]
        off = GC.find_stage_tables(self.game.code)
        self.assertEqual(diff, [off + 18, off + 19, off + 32 + 9])
        self.assertEqual(code[off + 18:off + 20], bytes([27, 27]))
        self.assertEqual(code[off + 41], 8)

    def test_default_pack_has_no_extras(self):
        self.assertEqual(self.base["starts"], [])
        self.assertEqual(self.base["map9"], "")
        self.assertTrue(MP.is_current(self.base))


if __name__ == "__main__":
    unittest.main()
