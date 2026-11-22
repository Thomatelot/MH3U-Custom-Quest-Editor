"""1.8.1: Monster pack starts (no writing over the game's start lists), reward tables A and B,
clean-up of the Citra folder."""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mhqe import gamedata as G, monsterpack as MP  # noqa: E402

ROMFS = os.environ.get("MHQE_ROMFS")
HAVE_UNICORN = importlib.util.find_spec("unicorn") is not None


def _ips(data: bytes):
    i, out = 5, []
    while data[i:i + 3] != b"EOF":
        off, n = int.from_bytes(data[i:i + 3], "big"), int.from_bytes(data[i + 3:i + 5], "big")
        i += 5
        if n == 0:
            rl = int.from_bytes(data[i:i + 2], "big")
            out.append((off, data[i + 2:i + 3] * rl))
            i += 3
        else:
            out.append((off, data[i:i + n]))
            i += n
    return out


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class PackAtBoot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = MP.GameFiles(ROMFS)
        G.set_region(cls.game.region)
        cls.tmp = Path(tempfile.mkdtemp())

    def test_start_data_is_this_game(self):
        rt = MP.runtime_starts(self.game.code, self.game.region)
        self.assertIsNotNone(rt)
        self.assertEqual(len(rt), 152)
        place = MP.read_placement(self.game.code, MP.find_placement_table(self.game.code, self.game.layout))
        for lst in place.values():
            for _st, p in lst:
                recs, _end = MP._records_at(self.game.code, p)
                self.assertEqual(len(rt[p]), len(recs))
                for r, f in zip(rt[p], recs):
                    self.assertEqual((r[:16], r[44:]), (f[:16], f[44:]))
                    self.assertEqual(f[16:44], bytes(28))       # zero in the file: written at boot

    @unittest.skipUnless(HAVE_UNICORN, "unicorn not installed (developer tool)")
    def test_no_byte_of_the_pack_is_rewritten_at_boot(self):
        """Run the game's static initialisers on the untouched code.bin: none may write where the pack
        puts something (1.8.0 put starts and lists in start lists that the game fills at boot)."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import build_start_records as B
        text_va, _p, text_size = self.game.layout["text"]
        writer, _mem, _failed = B.run_inits(self.game.code, B.init_table(self.game.code, text_va + text_size))
        extras = {"starts": [{"em": 3, "map": 13, "area": 4, "form": 0, "flag": None},
                             {"em": 3, "map": 13, "area": 8, "form": 1, "flag": 0},
                             {"em": 74, "map": 1, "area": 9, "form": 1},
                             {"em": 41, "map": 2, "area": 3, "form": 2, "flag": 1}],
                  "roaming": {230: [[1, 2, 100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]]}, "map9": "port"}
        man = MP.build(ROMFS, self.tmp / "boot", log=lambda s: None, extras=extras)
        self.assertEqual(len(man["starts"]), 4)
        hit = [off + k + MP.BASE for off, blob in _ips((self.tmp / "boot" / "exefs" / "code.ips").read_bytes())
               for k in range(len(blob)) if off + k + MP.BASE in writer]
        self.assertEqual(hit, [])

    def test_hyper_peco_starts(self):
        """A tester's quest: Qurupeco on the Misty Peaks in area 4 and in area 8 (Super 1)."""
        starts = [{"em": 3, "map": 13, "area": 4, "form": 0, "flag": None},
                  {"em": 3, "map": 13, "area": 8, "form": 1, "flag": 0}]
        man = MP.build(ROMFS, self.tmp / "peco", log=lambda s: None, extras={"starts": starts})
        code = bytearray(self.game.code)
        for off, blob in _ips((self.tmp / "peco" / "exefs" / "code.ips").read_bytes()):
            code[off:off + len(blob)] = blob
        table = MP.find_placement_table(self.game.code, self.game.layout)
        import struct
        lst = MP.resolve_list(bytes(code), struct.unpack_from("<I", code, table - MP.BASE + 4 * 3)[0])
        recs, _end = MP._records_at(bytes(code), lst[12])
        self.assertEqual([(r[9], r[11], r[12]) for r in recs], [(6, 0, 0), (7, 0, 0), (4, 0, 0), (8, 1, 0)])
        rt = MP.runtime_starts(self.game.code, self.game.region)
        place = MP.read_placement(self.game.code, table)
        own = rt[dict(place[3])[12]]
        self.assertEqual([r[16:44] for r in recs[:2]], [r[16:44] for r in own])        # its own positions
        rathian = [r for r in rt[dict(place[1])[12]] if r[9] == 8][0]
        self.assertEqual(recs[3][16:44], rathian[16:44])                               # Rathian's point in area 8
        self.assertEqual(recs[2][8], 0xFF)                     # not the pack-leader byte of Great Jaggi's start
        self.assertEqual([x["start_from"] for x in man["starts"]], [12, 1])


def _game_quests():
    from mhqe import arc as arcmod
    from mhqe.quest import Quest
    region = MP.detect_region(ROMFS)
    a = arcmod.read(Path(ROMFS) / "arc" / "quest" / region / "quest00.arc")
    return {Quest(e.data).get("quest_no"): Quest(e.data) for e in a.entries if e.leaf.startswith("q_")}


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class RewardTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        G.set_region(MP.detect_region(ROMFS))
        cls.quests = _game_quests()

    def test_every_game_table_adds_up_to_100(self):
        n = 0
        for no, q in self.quests.items():
            for t in "AB":
                rows = q.rewards(t)
                if rows:
                    n += 1
                    self.assertIn(sum(c for _i, _q, c in rows), (100, 110), (no, t))
        self.assertGreater(n, 600)

    def test_tables_alternate_and_go_on_past_the_others_end(self):
        """The tester's example (a Gobul quest made from 'The Horned Wyvern'): table B ends at slot 15,
        table A goes on with Exquisite Meat 5 % at slot 16."""
        import struct
        q = self.quests[11204].copy()
        raw = [(1427, 1, 0), (37, 1, 0), (239, 2, 13), (37, 1, 15), (285, 1, 21), (239, 2, 30), (555, 1, 22),
               (1004, 1, 5), (552, 1, 12), (237, 2, 10), (549, 2, 0), (92, 20, 20), (558, 1, 12), (91, 20, 20),
               (303, 1, 15), (0, 0, 0), (1427, 1, 5)]
        for i in range(64):
            struct.pack_into("<HBB", q.data, q._rewards_start + 4 * i, *(raw[i] if i < len(raw) else (0, 0, 0)))
        self.assertEqual(q.reward_a[-1], (1427, 1, 5))
        self.assertEqual(len(q.reward_a), 9)
        self.assertEqual(sum(c for _i, _n, c in q.reward_a), 100)
        self.assertEqual(len(q.reward_b), 7)
        self.assertEqual(sum(c for _i, _n, c in q.reward_b), 100)
        q.set_rewards("B", q.reward_b + [(91, 1, 0)])
        self.assertEqual(q.reward_a[-1], (1427, 1, 5))          # writing B leaves A alone
        self.assertEqual(struct.unpack_from("<HBB", q.data, q._rewards_start + 4 * 15), (91, 1, 0))

    def test_lagombi_quest_keeps_its_last_rows(self):
        q = next(q for q in self.quests.values() if q.get_text("name", 0).endswith("Forecast: Lagombi"))
        self.assertEqual(sum(c for _i, _n, c in q.reward_a), 100)     # 1.8.0 lost the last two rows

    def test_ceadeus_gets_its_materials(self):
        from mhqe import autofill as AF
        q = self.quests[2502].copy()                                   # Save Moga Village!
        for pool in ("HR", "G"):
            a, b, _text = AF.reward_plan(q, pool)
            mats = [i for i, _n, _c in a if 20 in AF.owners_of(i)]
            self.assertGreaterEqual(len(mats), 4, pool)
            self.assertEqual(sum(c for _i, _n, c in a), 100)
            self.assertEqual(sum(c for _i, _n, c in b), 100)

    def test_to_100(self):
        from mhqe import autofill as AF
        rows = [(1, 1, 0), (2, 1, 30), (3, 1, 30), (4, 1, 60)]
        out = AF.to_100(rows)
        self.assertEqual(out[0], (1, 1, 0))
        self.assertEqual(sum(c for _i, _n, c in out), 100)


class CleanUp(unittest.TestCase):
    def setUp(self):
        import json
        from mhqe import supp
        self.tmp = Path(tempfile.mkdtemp())
        self.title = self.tmp / "Citra" / "load" / "mods" / "00040000000AE400"
        t = self.title
        files = {
            "exefs/code.ips": b"PATCHEOF", MP.MANIFEST: json.dumps({"monsters": [3, 51]}).encode(),
            "romfs/arc/enemy/em003.arc": b"a", "romfs/arc/enemy/em051.arc": b"b",
            "romfs/quest/us/q_11314.quest": b"q", "romfs/quest/us/quest.list": b"l",
            "romfs/arc/quest/us/quest00.arc": b"arc",
            # another mod's files: kept
            "romfs/quest/btl/q_11314.quest_btl": b"btl", "romfs/arc/ID/ID_resi_eng.arc": b"font",
        }
        if supp.SPARE:
            files[f"romfs/quest/support/{supp.file_name(supp.SPARE[0])}"] = b"supp"
        for rel, data in files.items():
            (t / rel).parent.mkdir(parents=True, exist_ok=True)
            (t / rel).write_bytes(data)
        self.files = files
        self.packs = self.tmp / "extdata" / "user"
        self.orig = self.tmp / "backups" / "original"
        self.packs.mkdir(parents=True)
        self.orig.mkdir(parents=True)
        for n in ("quest1", "quest2"):
            (self.orig / n).write_bytes(b"original " + n.encode())
        (self.packs / "quest1").write_bytes(b"changed")
        (self.packs / "quest2").write_bytes(b"original quest2")

    def test_only_the_editors_files(self):
        from mhqe import cleanup
        found = {p.relative_to(self.title).as_posix() for p in cleanup.editor_mod_files([self.title])}
        self.assertEqual(found, {k for k in self.files if "btl" not in k and "ID_resi" not in k})

    def test_remove_then_put_back(self):
        from mhqe import cleanup
        mods = cleanup.editor_mod_files([self.title])
        dest, errors = cleanup.remove_mods(mods, [self.title], self.tmp / "backups")
        self.assertEqual(errors, [])
        self.assertTrue((self.title / "romfs/quest/btl/q_11314.quest_btl").is_file())
        self.assertTrue((self.title / "romfs/arc/ID/ID_resi_eng.arc").is_file())
        self.assertFalse(any(p.is_file() for p in mods))
        self.assertFalse((self.title / "exefs").exists())                 # emptied folders go too
        lc = cleanup.last_cleanup(self.tmp / "backups")
        self.assertEqual(lc[0], dest)
        self.assertEqual(cleanup.put_back(dest), len(mods))
        for rel, data in self.files.items():
            self.assertEqual((self.title / rel).read_bytes(), data, rel)
        self.assertIsNone(cleanup.last_cleanup(self.tmp / "backups"))

    def test_back_to_before_the_editor(self):
        from mhqe import cleanup
        pairs = cleanup.changed_event_files(self.packs, self.orig)
        self.assertEqual([p[0].name for p in pairs], ["quest1"])
        dest, removed, put, errors = cleanup.back_to_before([self.title], self.packs, self.orig, self.tmp / "backups")
        self.assertEqual((put, errors), (1, []))
        self.assertGreater(removed, 5)
        self.assertEqual((self.packs / "quest1").read_bytes(), b"original quest1")
        cleanup.put_back(dest)
        self.assertEqual((self.packs / "quest1").read_bytes(), b"changed")


if __name__ == "__main__":
    unittest.main()
