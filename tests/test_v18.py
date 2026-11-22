"""Tests for version 1.8: testers' reports (picker crash, star ranks, phone import fallbacks, portable
Citra, monster data load). The game-file tests need MHQE_ROMFS (romfs folder of the game)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mhqe import gamedata as G  # noqa: E402

ROMFS = os.environ.get("MHQE_ROMFS")

try:
    import tkinter  # noqa: F401
    HAVE_TK = True
except ImportError:
    HAVE_TK = False


class _Icons:
    def monster(self, *_a):
        return None


@unittest.skipUnless(HAVE_TK, "tkinter not available")
class MonsterPicker(unittest.TestCase):
    def test_none_sorts_with_the_boulders(self):
        """1.7.0 crashed ('<' between tuple and int) when '(none)' and a boulder shared 'Other'."""
        from mhqe import picker
        for small_first in (False, True):
            for view in picker.monster_views(small_first):
                entries = picker.monster_entries(_Icons(), True, True)
                picker.sort_entries(entries, view)
                other = [e["key"] for e in entries if e[view[1]] == "Other"]
                self.assertEqual(other[0], 0)            # (none) first in its group
                self.assertGreater(len(other), 1)

    def test_mixed_order_keys(self):
        from mhqe import picker
        view = ("x", "g", ("A",))
        entries = [{"g": "A", "g_order": (2, "b")}, {"g": "A", "g_order": 1}, {"g": "A"}]
        picker.sort_entries(entries, view)
        self.assertEqual([e.get("g_order") for e in entries], [None, 1, (2, "b")])


class StarRanks(unittest.TestCase):
    def test_phone_clamps_to_nine(self):
        from mhqe import phone
        sys.path.insert(0, os.path.dirname(__file__))
        from test_phone import draft
        self.assertEqual(phone.clean(draft(star=10))["star"], 9)

    @unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
    def test_no_game_quest_above_nine(self):
        from mhqe.project import RomSource
        rom = RomSource(ROMFS, workspace=Path(tempfile.mkdtemp()), load_edits=False)
        self.assertLessEqual(max(q.get("star") for q in rom.quests.values()), 9)


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class PhoneFallbacks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mhqe.project import RomSource
        rom = RomSource(ROMFS, workspace=Path(tempfile.mkdtemp()), load_edits=False)
        cls.cands = [(q.get_text("name", 0), q, "Game quests") for _no, q in sorted(rom.quests.items())]

    def make(self, **kw):
        from mhqe import phone
        from mhqe.quest import Quest
        sys.path.insert(0, os.path.dirname(__file__))
        from test_phone import draft
        d = phone.clean(draft(**kw))
        hit = phone.find_template(d, self.cands)
        self.assertIsNotNone(hit, f"no template for map {d['map']}")
        q = hit[1].copy()
        notes = phone.apply(q, d, source_no=hit[1].get("quest_no"))
        return Quest(q.to_bytes()), hit[3], notes

    def test_every_map_has_a_template(self):
        for m in G.MAP_NAMES:
            q, _how, _notes = self.make(map=m)
            self.assertEqual(q.get("map"), m)

    def test_great_desert_keeps_the_dragonship(self):
        from mhqe import siege
        q, how, _notes = self.make(map=6, monsters=[{"em": 1, "count": 1}])
        self.assertIn("siege", how)
        self.assertEqual(q.objective(1)[2], 1)
        self.assertEqual(q.objective(2)[0], siege.SHIP_OBJ)
        self.assertEqual(q.get("clr_pattern"), 0)
        q, _how, _notes = self.make(map=6, monsters=[{"em": 25, "count": 1}])
        self.assertTrue(siege.ship_ok(q))

    def test_arena_variants_copy_the_same_arena(self):
        for m, sib in ((9, 8), (10, 12)):
            q, how, _notes = self.make(map=m)
            self.assertEqual(q.get("map"), m)
            self.assertIn(G.map_name(sib), how)


class PortableCitra(unittest.TestCase):
    def setUp(self):
        from mhqe import project
        self.p = project
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(project.set_extra_roots)

    def citra(self, *, nand=True):
        user = self.tmp / "citra-portable" / "user"
        save = user / "sdmc" / "Nintendo 3DS" / ("0" * 32) / ("0" * 32) / "extdata" / "00000000" / G.EXTDATA_ID / "user"
        save.mkdir(parents=True)
        if nand:
            (user / "nand").mkdir()
        return user, save

    def test_root_of(self):
        user, save = self.citra()
        for f in (user.parent, user, user / "sdmc", save):
            self.assertEqual(self.p.citra_root_of(f), user)
        self.assertIsNone(self.p.citra_root_of(self.tmp))

    def test_save_folder_gives_the_mod_folder(self):
        user, save = self.citra()
        self.p.set_extra_roots(derived=[save])
        want = user / "load" / "mods" / G.TITLE_ID / "romfs"
        self.assertEqual(self.p.find_emulator_mod_dirs()[0], want)
        self.assertEqual(self.p.find_emulator_title_dirs()[0], want.parent)
        self.assertEqual(self.p.find_emulator_pack_dirs()[0], save)

    def test_copy_of_a_real_3ds_is_left_alone(self):
        user, save = self.citra(nand=False)
        self.p.set_extra_roots(derived=[save])
        self.assertNotIn(user / "load" / "mods" / G.TITLE_ID / "romfs", self.p.find_emulator_mod_dirs())
        self.p.set_extra_roots(chosen=[user.parent])                  # unless chosen as Citra's folder
        self.assertEqual(self.p.find_emulator_mod_dirs()[0], user / "load" / "mods" / G.TITLE_ID / "romfs")


class MonsterLoad(unittest.TestCase):
    def test_data(self):
        from mhqe import loadsize
        self.assertTrue(loadsize.available())
        self.assertGreater(loadsize.size(75), loadsize.size(1))           # Dire Miralis is the heaviest
        self.assertGreater(loadsize.kind_max(1), loadsize.game_max(3))

    @unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
    def test_game_quests_never_warn_and_a_crowd_does(self):
        from mhqe import loadsize
        from mhqe.project import RomSource
        rom = RomSource(ROMFS, workspace=Path(tempfile.mkdtemp()), load_edits=False)
        for no, q in rom.quests.items():
            self.assertFalse([t for lv, t in loadsize.problems(q) if lv == "warning"], no)
        q = rom.quests[11657].copy()                                    # Flooded Forest
        for i, em in enumerate((45, 18, 15, 46)):
            q.set_monster(i, Type=em)
        self.assertEqual(loadsize.problems(q)[0][0], "warning")
        self.assertIn("MB", loadsize.summary(q))

    def test_roaming_counts_as_many_as_roam_at_once(self):
        from mhqe import loadsize, strays

        class Q:
            monsters = [{"Type": 1}]
            vals = {"nora_set_per": 50, "nora_set_table": 0, "nora_set_max": 1, "main_zako1": 0, "main_zako2": 0}

            def get(self, k):
                return self.vals.get(k, 0)
        idx = next(i for i, t in strays.game_tables().items() if len({e[0] for e in t}) > 2)
        q = Q()
        q.vals["nora_set_table"] = idx
        self.assertEqual(sum(1 for k in loadsize.species(q).values() if k == "roaming"), 1)
        q.vals["nora_set_max"] = 2
        self.assertEqual(sum(1 for k in loadsize.species(q).values() if k == "roaming"), 2)


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class UnderwaterRuin(unittest.TestCase):
    def test_notes(self):
        from mhqe import rules, validate
        from mhqe.project import RomSource
        rom = RomSource(ROMFS, workspace=Path(tempfile.mkdtemp()), load_edits=False)
        q = rom.quests[11825].copy()                                    # Abyssal Awakening: hunters in area 3
        self.assertFalse([i for i in validate.validate_quest(q) if "area 1 is closed" in i.text])
        q.set("supp_enemy_num", 0)
        self.assertTrue([i for i in validate.validate_quest(q) if "area 1 is closed" in i.text])
        rules.set_night(q, True)
        self.assertEqual(rules.time_note(q)[0], "info")
        self.assertIn("everything worked", rules.time_warning(q))

    def test_night_versions_match_the_stage_table(self):
        from mhqe import gamecode as GC, rules
        for m in rules.DAY_ONLY_MAPS:
            day, night = GC.STAGE_TABLE[2 * m], GC.STAGE_TABLE[2 * m + 1]
            self.assertEqual(m in rules.UNUSED_NIGHT, night != day, m)
            if m in rules.UNUSED_NIGHT:
                self.assertEqual(rules.UNUSED_NIGHT[m], night)


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class PhoneOptions(PhoneFallbacks):
    """Notebook 1.1: hunters start, roaming monsters, start areas, strength rows, small monsters,
    supply box."""
    def test_new_options(self):
        from mhqe import phone, spawns, startpos, strays
        q, _how, _notes = self.make(
            map=1, star=6, hub="Port", rank=4, hunters=1, environment="unstable", small="none",
            small_rows=[20, 21, 3], supply=134,
            monsters=[{"em": 1, "count": 1, "size": 100, "rows": [40, 50, 30], "start": 1}])
        self.assertEqual(q.get("supp_enemy_num"), 1)
        self.assertTrue(strays.is_unstable(q))
        self.assertEqual(spawns.records(q), [])
        self.assertEqual((q.get("zako_nando_hp"), q.get("zako_nando_at"), q.get("zako_nando_etc")), (20, 21, 3))
        self.assertEqual(q.get("item_set_no"), 134)
        m = q.monsters[0]
        self.assertEqual((m["Nando_hp"], m["Nando_at"], m["Nando_etc"], m["Starttype"]), (40, 50, 30, 1))
        self.assertGreater(len(startpos.areas(1, 1)), 1)

    def test_small_monsters_from_a_base_game_quest(self):
        """A base-game quest is shorter than an event slot: the copy gets room for its small monsters
        (before 1.8 a phone quest made from one had none)."""
        from mhqe import spawns
        q, _how, _notes = self.make(map=1, star=6, hub="Port", rank=4)
        self.assertTrue(spawns.readable(q))
        self.assertGreater(len(spawns.records(q)), 0)
        q, _how, _notes = self.make(map=1, star=6, hub="Port", rank=4, small="none")
        self.assertTrue(spawns.readable(q))
        self.assertEqual(spawns.records(q), [])

    def test_stable_and_bad_start(self):
        from mhqe import strays
        q, _how, notes = self.make(map=1, environment="stable",
                                   monsters=[{"em": 1, "count": 1, "start": 9}])
        self.assertFalse(strays.is_unstable(q))
        self.assertEqual(q.monsters[0]["Starttype"], 0)
        self.assertTrue(any("start chosen" in n for n in notes))

    def test_old_drafts_keep_their_meaning(self):
        from mhqe import phone
        sys.path.insert(0, os.path.dirname(__file__))
        from test_phone import draft
        d = phone.clean(draft())
        self.assertEqual((d["hunters"], d["environment"], d["small"], d["supply"]), (None, None, "auto", None))
        self.assertIsNone(d["monsters"][0]["rows"])
        bad = phone.clean(draft(supply=99999, small_rows=[1, 2], hunters=7))
        self.assertEqual((bad["supply"], bad["small_rows"], bad["hunters"]), (None, None, 2))


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class RoamingTable(unittest.TestCase):
    """Lists past the game's table (214-255): the pack moves the table (two pointers in code.bin)."""
    def test_lists_past_the_table(self):
        import struct
        from mhqe import gamecode as GC, monsterpack as MP, strays
        sys.path.insert(0, os.path.dirname(__file__))
        from test_v15 import _apply_ips
        game = MP.GameFiles(ROMFS)
        tmp = Path(tempfile.mkdtemp())
        like = strays.game_tables()[2][0]
        lists = {"37": [strays.make_entry(1, 100, like)], "214": [strays.make_entry(2, 60, like),
                 strays.make_entry(7, 40, like)], "255": [strays.make_entry(15, 100, like)]}
        man = MP.build(ROMFS, tmp / "p", log=lambda s: None, extras={"roaming": lists})
        self.assertTrue(MP.extras_match(man, {"roaming": lists}))
        self.assertEqual(man["roaming_table"]["slots"], 256)
        code0 = game.code
        code = _apply_ips(code0, (tmp / "p" / "exefs" / "code.ips").read_bytes())
        old_va, ptrs0 = GC.find_roaming(code0)
        old_va += GC.BASE
        new_va = int(man["roaming_table"]["table"], 16)
        # the two words that pointed to the game's table now point to the copy, and nothing else does
        lits = [i for i in range(0, len(code0) - 3, 4) if struct.unpack_from("<I", code0, i)[0] == old_va]
        self.assertEqual(len(lits), 2)
        for i in lits:
            self.assertEqual(struct.unpack_from("<I", code, i)[0], new_va)
        new = list(struct.unpack_from("<256I", code, new_va - GC.BASE))
        for idx, p in enumerate(ptrs0):                    # the game's lists unchanged
            if str(idx) not in lists:
                self.assertEqual(new[idx], p, idx)
        for k, entries in lists.items():                    # yours readable where the game looks
            got = GC._read_list(code, new[int(k)] - GC.BASE)
            self.assertEqual(got, entries)
        for idx in range(214, 256):
            if str(idx) not in lists:
                self.assertEqual(new[idx], 0)

    def test_three_monsters_at_most(self):
        from mhqe import strays
        like = strays.game_tables()[2][0]
        four = [strays.make_entry(em, 25, like) for em in (1, 2, 7, 15)]
        self.assertTrue(any("first 3" in p for p in strays.table_problems(four)))
        self.assertFalse(strays.table_problems([strays.make_entry(1, 100, like)]))


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class RoamingSettings(unittest.TestCase):
    def test_unstable_does_not_copy_a_qurupeco_only_setting(self):
        from mhqe import strays
        for m in (1, 2, 3, 4, 5, 13):
            for star in range(1, 10):
                refs = strays.references(m, star)
                if any(not r["pekko"] for r in refs):
                    self.assertFalse(refs[0]["pekko"], (m, star))

    def test_pekko_without_qurupeco_is_reported(self):
        from mhqe import strays
        from mhqe.project import RomSource
        rom = RomSource(ROMFS, workspace=Path(tempfile.mkdtemp()), load_edits=False)
        q = rom.quests[1302].copy()                       # Playing with Fire: Qurupeco, only when called
        self.assertEqual(q.get("nora_pekko"), 1)
        self.assertFalse([p for p in strays.problems(q) if "no Qurupeco" in p])
        q.set_monster(0, Type=1)
        self.assertTrue([p for p in strays.problems(q) if "no Qurupeco" in p])


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class BorrowedPositions(unittest.TestCase):
    """A start of your own in an area where the monster has no position: the pack copies the
    positions of another monster there (testers' request: any area, any kind)."""
    def test_editor_and_pack_agree(self):
        """The start point the dialog names is the one the pack copies."""
        from mhqe import monsterpack as MP, startpos
        game = MP.GameFiles(ROMFS)
        rt = MP.runtime_starts(game.code, game.region)
        self.assertIsNotNone(rt)
        place = MP.read_placement(game.code, MP.find_placement_table(game.code, game.layout))
        for em in (1, 3, 7, 15, 41, 74):
            for m in (1, 2, 3, 4, 5, 13):
                st = G.MAP_TO_INTERNAL[m]
                own = dict(place[em]).get(st)
                if own is None:
                    continue
                for area, donor in startpos.start_area_choices(em, m):
                    _r, owner = MP.start_template(rt, place, em, st, area, rt[own])
                    self.assertEqual(owner, donor, (em, m, area))
                self.assertNotIn(0, [a for a, _d in startpos.start_area_choices(em, m)] if m != 7 else [])

    def test_build_with_a_borrowed_area(self):
        from mhqe import monsterpack as MP, startpos
        sys.path.insert(0, os.path.dirname(__file__))
        em, m = 3, 13                                  # Qurupeco on the Misty Peaks (HYPER PECO, a tester's quest)
        own = set(startpos.areas(em, m, game_only=True))
        choices = dict(startpos.start_area_choices(em, m))
        self.assertEqual(choices.get(8), 1)            # area 8: Rathian's start point
        self.assertNotIn(8, own)
        tmp = Path(tempfile.mkdtemp())
        starts = [{"em": em, "map": m, "area": 4, "form": 0, "flag": None},
                  {"em": em, "map": m, "area": 8, "form": 1, "flag": 0}]
        man = MP.build(ROMFS, tmp / "p", log=lambda s: None, extras={"starts": starts})
        x = man["starts"][1]
        self.assertEqual((x["area"], x["start_from"], x["index"]), (8, 1, 3))
        area, donor = 8, 1
        from mhqe import arc
        a = arc.read(tmp / "p" / "romfs" / "arc" / "enemy" / f"em{em:03d}.arc")
        e = next(e for e in a.entries if e.leaf == "em_mappos00")
        st = MP.SpawnTable.parse(e.data).stages[G.MAP_TO_INTERNAL[m]]
        self.assertIn(area, st)
        self.assertEqual(sorted(st), sorted(st))
        donor_pos = MP.MonsterData(MP.GameFiles(ROMFS).archive(donor).read_bytes()).spawn.stages[
            G.MAP_TO_INTERNAL[m]][area].pos
        self.assertEqual(st[area].pos, donor_pos)
        self.assertEqual(set(st) - {area}, set(startpos.spawn_areas(em, m)))       # its own areas unchanged

    def test_base_camp_is_refused(self):
        from mhqe import startpos
        probs = startpos.custom_problems({"em": 1, "map": 3, "area": 0, "form": 0, "flag": None})
        self.assertTrue(any("base camp" in p for p in probs))


if __name__ == "__main__":
    unittest.main()
