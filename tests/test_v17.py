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
                if st in lst:                           # the game takes the first entry of a stage
                    continue
                recs, end = MP._records_at(code, q)
                # without the position (+16..+43): zero in the game's file, written at boot
                lst[st] = ([r[4:16] + r[44:] for r in recs], end)
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
                    # the new list carries the start positions (the game's own list gets them at boot)
                    p = MP.resolve_list(code, struct.unpack_from("<I", code, self.table - MP.BASE + 4 * em)[0])[st]
                    recs, _end = MP._records_at(code, p)
                    rt = MP.runtime_starts(self.game.code, self.game.region)
                    q0 = MP.resolve_list(self.code0, struct.unpack_from("<I", self.code0, self.table - MP.BASE
                                                                        + 4 * em)[0])[st]
                    for r, r0 in zip(recs, rt.get(q0) or MP._records_at(self.code0, q0)[0]):
                        self.assertEqual(r[16:44], r0[16:44], (em, st))
                    if st != MP.DESERT:                 # the Great Desert list of the pack has none (1.4)
                        self.assertTrue(any(recs[-1][16:28]), (em, st))
                else:
                    self.assertEqual(len(rb[0]), len(ra[0]))

    def test_nothing_is_written_over_the_games_start_lists(self):
        """1.8.0 shared the game's duplicate start lists and wrote over the freed ones, but a static
        initialiser writes the start positions there at boot: nothing may go there."""
        man = MP.build(ROMFS, self.tmp / "own", log=lambda s: None,
                       extras={"starts": [{"em": 74, "map": 1, "area": 9, "form": 1},
                                          {"em": 3, "map": 13, "area": 8, "form": 1, "flag": 0}],
                               "roaming": {230: [[1, 2, 100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]]}})
        self.assertEqual(len(man["starts"]), 2)
        self.assertIn("start_positions", man["features"])
        self.assertFalse(MP.broken_starts(man))
        place = MP.read_placement(self.game.code, self.table)
        lo, hi = MP.start_lists_span(self.game.code, place)
        data = (self.tmp / "own" / "exefs" / "code.ips").read_bytes()
        i = 5
        while data[i:i + 3] != b"EOF":
            off, n = int.from_bytes(data[i:i + 3], "big"), int.from_bytes(data[i + 3:i + 5], "big")
            self.assertTrue(off + n <= lo - MP.BASE or off >= hi - MP.BASE, hex(off + MP.BASE))
            i += 5 + n
        # every placement list reads as the default pack's, but the two starts of your own
        code = _apply_ips(self.game.code, data)
        for em in range(86):
            pa = struct.unpack_from("<I", self.code0, self.table - MP.BASE + 4 * em)[0]
            pb = struct.unpack_from("<I", code, self.table - MP.BASE + 4 * em)[0]
            ra = MP.resolve_list(self.code0, pa) if pa else {}
            rb = MP.resolve_list(code, pb) if pb else {}
            self.assertEqual(set(ra), set(rb), em)
            for st in ra:
                if (em, st) not in {(74, 1), (3, 12)}:
                    self.assertEqual(MP._records_at(self.code0, ra[st]), MP._records_at(code, rb[st]), (em, st))

    def test_old_packs_with_starts_are_flagged(self):
        old = {"features": ["big_sizes", "desert_area2", "siege_bosses"], "starts": [{"em": 3}]}
        self.assertTrue(MP.broken_starts(old))
        self.assertFalse(MP.is_current(old))
        self.assertFalse(MP.broken_starts({"features": ["big_sizes", "desert_area2", "siege_bosses"], "starts": []}))
        from mhqe import arc as arcmod, validate
        from mhqe.quest import Quest
        region = MP.detect_region(ROMFS)
        a = arcmod.read(Path(ROMFS) / "arc" / "quest" / region / "quest00.arc")
        q = Quest(next(e.data for e in a.entries if e.leaf.startswith("q_") and Quest(e.data).monsters[0]["Type"]))
        texts = [i.text for i in validate.validate_quest(q, monster_pack=old)]
        self.assertTrue(any("1.8.0" in t for t in texts))

    def test_chained_placement_lists(self):
        lists = {1: [(1, 10), (2, 20), (3, 30)], 2: [(1, 11), (2, 20), (3, 30)], 3: [(1, 10), (2, 20)]}
        todo = dict(lists)
        chain = MP.next_chain(todo, 1 << 20)
        self.assertFalse(todo)
        blob, offs = MP.chain_blob(chain)
        code = bytes(0x100) + blob
        for em, lst in lists.items():
            self.assertEqual(MP.resolve_list(code, MP.BASE + 0x100 + offs[em]), dict(lst))
        self.assertLess(len(blob), sum(8 * (len(v) + 1) for v in lists.values()))

    def test_a_wrong_area_keeps_the_pack_built_before(self):
        out = self.tmp / "keep"
        MP.build(ROMFS, out, log=lambda s: None)
        with self.assertRaises(MP.PackError):
            MP.build(ROMFS, out, log=lambda s: None, extras={"starts": [{"em": 74, "map": 1, "area": 0}]})   # the camp: the game starts no monster there
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
