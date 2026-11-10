"""Tests for version 1.3 features. Most need no game files; the big-size test needs
MHQE_ROMFS (romfs folder of the game, with exefs/code.bin next to it)."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mhqe import backup as B          # noqa: E402
from mhqe import i18n, monsterpack as MP   # noqa: E402

ROMFS = os.environ.get("MHQE_ROMFS")


class RollingBackups(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.save = root / "user"
        self.save.mkdir()
        for n in ("quest1", "quest2", "quest3", "quest4"):
            (self.save / n).write_bytes(b"first " + n.encode())
        self.b = B.BackupManager(root / "backups", keep_full=3, keep_per_quest=2)
        self._n = 0
        B._stamp = self._stamp                      # distinct, ordered names without waiting

    def _stamp(self):
        self._n += 1
        return time.strftime("2026-01-01_00-00-") + f"{self._n:02d}"

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_backups_roll_but_first_and_originals_stay(self):
        first = self.b.snapshot(self.save.iterdir())
        for i in range(10):
            (self.save / "quest1").write_bytes(f"edit {i}".encode())
            self.b.snapshot(self.save.iterdir())
        fulls = [s for s in self.b.list_full() if s["kind"] == "full"]
        self.assertEqual(len(fulls), 4)                         # 3 newest + the protected first one
        self.assertIn(first, [s["path"] for s in fulls])
        self.assertEqual((first / "quest1").read_bytes(), b"first quest1")
        self.assertEqual((self.b.original_dir / "quest1").read_bytes(), b"first quest1")
        self.assertEqual(self.b.protected_full(), first)

    def test_quest_backups_roll_per_quest_and_keep_the_first(self):
        for i in range(8):
            self.b.save_quest(f"v{i}".encode(), pack="quest1", slot=0, quest_no=20001, name="A", reason="edited")
            self.b.save_quest(f"w{i}".encode(), pack="quest1", slot=1, quest_no=20002, name="B", reason="edited")
        for no in (20001, 20002):
            items = [x for x in self.b.list_quests() if x["quest_no"] == no]
            self.assertEqual(len(items), 3)                     # 2 newest + the first
            data = sorted(x["path"].read_bytes() for x in items)
            self.assertIn(b"v0" if no == 20001 else b"w0", data)

    def test_failsafe_never_deletes_outside_or_originals(self):
        self.b.snapshot(self.save.iterdir())
        self.assertFalse(self.b._deletable(self.b.original_dir, self.b.full_dir))
        self.assertFalse(self.b._deletable(self.b.original_dir / "quest1", self.b.full_dir))
        self.assertFalse(self.b._deletable(self.save / "quest1", self.b.full_dir))
        self.assertFalse(self.b._deletable(self.save, self.save.parent))
        self.b.prune(keep=0)
        self.b.prune_quests(keep=0)
        self.assertTrue(all((self.save / n).exists() for n in ("quest1", "quest2", "quest3", "quest4")))
        self.assertTrue((self.b.original_dir / "quest1").exists())

    def test_old_setups_protect_their_oldest_backup(self):
        a = self.b.snapshot(self.save.iterdir())
        info = a / "info.json"
        info.write_text(info.read_text().replace('"protected": true', '"protected": false'))
        for _ in range(6):
            self.b.snapshot(self.save.iterdir())
        self.assertIn(a, [s["path"] for s in self.b.list_full()])


if __name__ == "__main__":
    unittest.main()


class BigSizes(unittest.TestCase):
    def test_split_and_full_size_round_trip(self):
        for pct in (0, 20, 100, 255, 256, 300, 999, 1000, 1550, 2000):
            size, spread = MP.split_size(pct)
            self.assertTrue(0 <= size <= 255)
            self.assertEqual(MP.full_size(size, spread if spread is not None else 0), pct)
        self.assertEqual(MP.full_size(150, 3), 150)          # the game's own spreads are not big sizes

    @unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
    def test_patched_table_gives_the_sizes(self):
        import struct
        game = MP.GameFiles(ROMFS)
        code = bytearray(game.code)
        table, lit = MP.find_size_table(bytes(code), game.layout)
        old = [struct.unpack_from("<I", code, table - MP.BASE + 4 * k)[0] for k in range(35)]
        at = MP.free_regions(bytes(code), game.layout)[0][0]
        blob = MP.big_size_blobs(bytes(code), table, at)
        code[at - MP.BASE:at - MP.BASE + len(blob)] = blob
        struct.pack_into("<I", code, lit, at)

        def roll(size, sp):        # what the game's function does, highest value of the range
            ptr = struct.unpack_from("<I", code, struct.unpack_from("<I", code, lit)[0] - MP.BASE + 4 * sp)[0]
            if not ptr:
                return size
            _w, _lo, hi = struct.unpack_from("<3H", code, ptr - MP.BASE)
            return size + hi - 100
        new = [struct.unpack_from("<I", code, at - MP.BASE + 4 * k)[0] for k in range(35)]
        self.assertEqual(new, old)                            # the game's 35 spreads are kept
        self.assertEqual(roll(200, 40), 200)                  # past the game's table: exact size now
        for pct in (300, 1000, 2000):
            size, sp = MP.split_size(pct)
            self.assertEqual(roll(size, sp), pct)


class French(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_exact_pattern_and_fallback(self):
        i18n.set_language("fr")
        self.assertEqual(i18n._("Save"), "Enregistrer")
        self.assertEqual(i18n._("Where Rathalos starts"), "Où commence Rathalos")
        self.assertEqual(i18n._("text that is not translated"), "text that is not translated")
        i18n.set_language("en")
        self.assertEqual(i18n._("Save"), "Save")


class Requirements(unittest.TestCase):
    def test_rules_and_board_lines(self):
        from mhqe import rules
        self.assertEqual(rules.rules_of(17, 0), rules.Req(3, 4, False))
        self.assertEqual(rules.rules_of(17, 13), rules.Req(3, 1, False))
        self.assertEqual(rules.rules_of(0, 12), rules.Req(None, 4, True))
        self.assertEqual(rules.conds_for(rules.Req(6, 4, True)), (20, 12))
        self.assertIsNone(rules.conds_for(rules.Req(6, 2, True)))
        self.assertEqual(rules.flag_for(rules.Req(3, 1, False), 0), 9)     # 'HR 3 ... Max participants: 1'
        self.assertEqual(rules.flag_for(rules.Req(5, 4, False), 0), 5)
        self.assertEqual(rules.flag_for(rules.Req(4, 2, False), 0), 4)      # no exact line: the HR line
        self.assertEqual(rules.problems(3, 17, 0), [])
        self.assertTrue(rules.problems(0, 17, 0))

    @unittest.skipUnless(os.environ.get("MHQE_PACK_DIR"), "MHQE_PACK_DIR not set")
    def test_challenge_gear_round_trip(self):
        from mhqe import arena
        from mhqe.packs import EventPack
        pk = EventPack(Path(os.environ["MHQE_PACK_DIR"]) / "quest4")
        q = next(s.quest for s in pk.used_slots() if arena.uses_gear(s.quest.get("quest_no")))
        before = bytes(q.data)
        self.assertTrue(arena.has_gear(q))
        p = arena.read_set(q, 0)
        self.assertIn(p[0][0], arena.WEAPON_TYPES)
        arena.write_set(q, 0, p)
        self.assertEqual(bytes(q.data), before)
        p[0] = [7, 1]
        arena.write_set(q, 0, p)
        self.assertEqual(arena.read_set(q, 0)[0], [7, 1])
        self.assertEqual(len(q.data), len(before))


@unittest.skipUnless(os.environ.get("MHQE_QUEST_DIR"), "MHQE_QUEST_DIR not set")
class Dragonship(unittest.TestCase):
    def load(self, n):
        from mhqe.quest import Quest
        return Quest((Path(os.environ["MHQE_QUEST_DIR"]) / f"q_{n:05d}.quest").read_bytes())

    def test_game_desert_quests_pass_and_setup_restores_them(self):
        from mhqe import rules, siege
        for n in (1712, 11823):
            game = self.load(n)
            self.assertTrue(siege.ship_ok(game))
            self.assertEqual(siege.problems(game), [])
            q = game.copy()
            q.set("category", (q.get("category") & ~siege.SHIP_BIT))
            q.set_objective(1, 0x4014, 70, 1, 0)          # a Ceadeus template's objectives
            q.set_objective(2, 0, 58, 1, 0)
            q.set("clr_pattern", 1)
            self.assertIn("error", [lv for lv, _t in siege.problems(q)])
            self.assertTrue(siege.apply_ship(q))
            for f in ("category", "clr_pattern", "obj1_param", "obj1_id", "obj1_num",
                      "obj2_param", "obj2_id", "obj2_num"):
                self.assertEqual(q.get(f), game.get(f), f)
            for lang in range(5):
                self.assertEqual(q.get_text("failure", lang), game.get_text("failure", lang))
        night = self.load(11823)
        self.assertTrue(rules.is_night(night))
        self.assertIsNone(rules.time_warning(night))       # the Great Desert has a night quest
