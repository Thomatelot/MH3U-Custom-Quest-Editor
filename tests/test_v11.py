"""Tests for version 1.1: game versions (EU/US) and the monster placement pack.

Environment variables (tests without their input are skipped):
  MHQE_ROMFS     romfs folder of an extracted MH3U (exefs/code.bin next to it): EU or US
  MHQE_ROMFS_US  romfs folder of the US version (optional, for the EU/US comparison)
Run:  python -m unittest discover -s tests -v
"""
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mhqe import gamedata as G, monsterpack as P, startpos       # noqa: E402
from mhqe.project import RomSource, find_pack_dir, pack_dir_region  # noqa: E402
from mhqe.quest import Quest                                       # noqa: E402
from mhqe.validate import validate_quest                           # noqa: E402

ROMFS = os.environ.get("MHQE_ROMFS")
ROMFS_US = os.environ.get("MHQE_ROMFS_US")


class Regions(unittest.TestCase):
    def tearDown(self):
        G.set_region("eu")

    def test_switch(self):
        G.set_region("us")
        self.assertEqual((G.TITLE_ID, G.EXTDATA_ID, G.REGION_DIR), ("00040000000AE400", "00000AE4", "us"))
        G.set_region("eu")
        self.assertEqual((G.TITLE_ID, G.EXTDATA_ID, G.REGION_DIR), ("00040000000B1D00", "00000B1D", "eu"))
        with self.assertRaises(ValueError):
            G.set_region("jp")

    def test_save_folder_follows_the_version(self):
        with tempfile.TemporaryDirectory() as t:
            for ext in ("00000B1D", "00000AE4"):
                d = Path(t, "sdmc", "Nintendo 3DS", "a", "b", "extdata", "00000000", ext, "user")
                d.mkdir(parents=True)
                (d / "quest1").write_bytes(b"")
            G.set_region("us")
            self.assertIn("00000AE4", str(find_pack_dir(t)))
            self.assertEqual(pack_dir_region(find_pack_dir(t)), "us")
            G.set_region("eu")
            self.assertIn("00000B1D", str(find_pack_dir(t)))


class StartAreas(unittest.TestCase):
    def test_map_numbers(self):
        self.assertEqual(startpos.area_label(1, 10), "area 8")         # Rathian's usual start, as the map shows it
        self.assertEqual(startpos.choice_text(0, startpos.areas(1, 1), 1),
                         "0  -  starts in area 8  (usual start)")
        self.assertIn("entrance", startpos.area_label(7, 0))

    def test_hunter_starts(self):
        self.assertEqual(startpos.hunter_text(7, 2), "Always in area 3.")
        self.assertIn("area 1 15%", startpos.hunter_text(1, 1))
        self.assertIsNone(startpos.hunter_warning(1, 1))
        self.assertIn("does nothing", startpos.hunter_warning(2, 2))

    def test_data(self):
        self.assertEqual(startpos.areas(1, 1), [10, 2, 5, 4])       # Rathian, Deserted Island
        self.assertEqual(startpos.areas(41, 13), [5, 6, 5])         # Zinogre, Misty Peaks (quest map 13)
        self.assertIsNone(startpos.areas(41, 2))                    # not allowed without the pack
        pack = {"added": [{"em": 41, "stage": 2, "donor": 44, "start_areas": [6, 7, 8]}]}
        self.assertEqual(startpos.areas(41, 2, pack), [6, 7, 8])

    def test_same_maps_as_placement(self):
        a = json.loads((G.DATA_DIR / "start_areas.json").read_text(encoding="utf-8"))["areas"]
        for em, stages in G.PLACEMENT.items():
            self.assertEqual({int(s) for s in a.get(str(em), {})}, stages, em)


class Checks(unittest.TestCase):
    @unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
    def test_pack_status_in_checks(self):
        src = RomSource(ROMFS, load_edits=False)
        q = Quest(src.originals[1101])
        q.set("map", 2)
        q.set_monster(0, Type=41, Num=1, Starttype=0)
        texts = lambda found: " ".join(i.text for i in found)     # noqa: E731
        found = validate_quest(q, in_pack=False)
        self.assertTrue(any(i.level == "error" and "Zinogre can not start" in i.text for i in found), texts(found))
        pack = {"added": [{"em": 41, "stage": 2, "donor": 44, "start_areas": [6, 7, 8]}]}
        found = validate_quest(q, in_pack=False, monster_pack=pack)
        self.assertFalse(any("can not start" in i.text for i in found), texts(found))
        self.assertTrue(any("Monster pack" in i.text for i in found))
        q.set_monster(0, Starttype=3)
        found = validate_quest(q, in_pack=False, monster_pack=pack)
        self.assertTrue(any(i.level == "error" and "start position 3" in i.text for i in found), texts(found))


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class Pack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "pack"
        cls.man = P.build(ROMFS, cls.out, log=lambda s: None)
        cls.game = P.GameFiles(ROMFS)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_siege_maps_follow_the_game(self):
        ruin = [a for a in self.man["added"] if a["stage"] == 7]
        self.assertTrue(ruin and all(a["donor"] == 69 and a["start_areas"] == [3] for a in ruin))  # Abyssal Lagiacrus

    def test_scope(self):
        ems = {a["em"] for a in self.man["added"]}
        self.assertFalse(ems & P.EXCLUDED_MONSTERS)
        self.assertEqual({a["stage"] for a in self.man["added"]}, set(range(1, 15)))      # every map, siege ones too
        for em in {a['em'] for a in self.man['added']}:
            self.assertEqual(len(G.PLACEMENT[em] | {a['stage'] for a in self.man['added'] if a['em'] == em}), 14, em)
        self.assertIn((41, 2), {(a["em"], a["stage"]) for a in self.man["added"]})
        z = [a for a in self.man["added"] if (a["em"], a["stage"]) == (41, 2)][0]
        self.assertEqual(z["donor"], 44)                       # Volvidon: the combination tested in the game

    def test_code_patch(self):
        code, orig = bytearray(self.game.code), self.game.code
        p = (self.out / "exefs" / "code.ips").read_bytes()
        self.assertTrue(p.startswith(b"PATCH") and p.endswith(b"EOF"))
        i = 5
        table = P.find_placement_table(orig, self.game.layout)
        regions = P.free_regions(orig, self.game.layout)
        while i < len(p) - 3:
            off, n = int.from_bytes(p[i:i + 3], "big"), int.from_bytes(p[i + 3:i + 5], "big")
            va = off + P.BASE
            self.assertTrue(any(a <= va and va + n <= b for a, b in regions) or table - 0x700 <= va < table + 4 * 86)
            code[off:off + n] = p[i + 5:i + 5 + n]
            i += 5 + n
        before, after = P.read_placement(orig, table), P.read_placement(bytes(code), table)
        added = {(a["em"], a["stage"]): a["donor"] for a in self.man["added"]}
        for em in range(86):
            for st, ptr in before[em]:
                self.assertEqual(dict(after[em])[st], ptr)
            game_lists = lambda st: {q for e2 in before for s_, q in before[e2] if s_ == st}   # noqa: E731
            for st in set(dict(after[em])) - set(dict(before[em])):
                self.assertIn(dict(after[em])[st], game_lists(st))      # one of the game's own start lists
        for a in self.man["added"]:
            self.assertEqual(P.start_areas(bytes(code), dict(after[a["em"]])[a["stage"]]), a["start_areas"])

    def test_archives(self):
        for em in self.man["monsters"]:
            f = self.out / "romfs" / "arc" / "enemy" / f"em{em:03d}.arc"
            if not f.exists():
                continue
            new, old = P.arc_entries(f.read_bytes()), P.arc_entries(self.game.archive(em).read_bytes())
            self.assertEqual(list(new), list(old))
            for k in new:
                if new[k] != old[k]:
                    self.assertTrue(k.rsplit("\\", 1)[-1].startswith("em_"), k)
            m = P.MonsterData(f.read_bytes())
            for a in self.man["added"]:
                if a["em"] == em and a["stage"] not in P.ROUTELESS_STAGES:
                    self.assertTrue(P.tables_complete(m, a["stage"]), (em, a["stage"]))

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as t:
            again = P.build(ROMFS, Path(t) / "p", log=lambda s: None)
        self.assertEqual(again["fingerprint"], self.man["fingerprint"])

    def test_install_uninstall(self):
        with tempfile.TemporaryDirectory() as t:
            mod = Path(t) / "mods" / "title"
            (mod / "romfs" / "quest" / "support").mkdir(parents=True)
            (mod / "romfs" / "quest" / "support" / "supp100.supp").write_bytes(b"x")   # another mod: kept
            P.install(self.out, mod)
            self.assertEqual(P.read_manifest(mod)["fingerprint"], self.man["fingerprint"])
            self.assertTrue((mod / "exefs" / "code.ips").is_file())
            P.uninstall(mod)
            self.assertFalse((mod / "exefs" / "code.ips").exists())
            self.assertFalse(list((mod / "romfs" / "arc" / "enemy").glob("*.arc")))
            self.assertTrue((mod / "romfs" / "quest" / "support" / "supp100.supp").is_file())
            (mod / "exefs" / "code.ips").write_bytes(b"PATCHEOF")          # someone else's code mod
            with self.assertRaises(P.PackError):
                P.install(self.out, mod)

    @unittest.skipUnless(ROMFS_US, "MHQE_ROMFS_US not set")
    def test_us_pack_is_the_same(self):
        with tempfile.TemporaryDirectory() as t:
            us = P.build(ROMFS_US, Path(t) / "p", log=lambda s: None)
            self.assertEqual(us["region"], "us")
            self.assertEqual(us["added"], self.man["added"])
            self.assertEqual(us["fingerprint"], self.man["fingerprint"])


@unittest.skipUnless(ROMFS_US, "MHQE_ROMFS_US not set")
class UsBaseGame(unittest.TestCase):
    def test_rom_source(self):
        src = RomSource(ROMFS_US, load_edits=False)
        self.assertEqual(src.region_dir, "us")
        self.assertEqual(len(src.originals), 365)
        with tempfile.TemporaryDirectory() as t:
            no = 1101
            src.quests[no].set("reward_money", src.quests[no].get("reward_money") + 1)
            src.modified.add(no)
            written = src.export_mod(t)
            names = sorted(str(Path(w).relative_to(t)).replace("\\", "/") for w in written)
            self.assertEqual(names, ["arc/quest/us/quest00.arc", "quest/us/q_01101.quest"])


if __name__ == "__main__":
    unittest.main()
