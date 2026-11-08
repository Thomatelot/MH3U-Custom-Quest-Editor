"""Core tests. They need YOUR game files, which are not distributed.

Set any of these environment variables (tests that lack their input are skipped):
  MHQE_QUEST_DIR  folder with loose q_NNNNN.quest files (romfs/quest/eu)
  MHQE_PACK_DIR   folder with quest1..quest4 (Citra extdata .../00000B1D/user)
  MHQE_ARC        path to romfs/arc/quest/eu/quest00.arc
  MHQE_CODE_BIN   path to exefs/code.bin
Run:  python -m unittest discover -s tests -v
"""
import glob
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mhqe import arc as arcmod, gamedata as G                      # noqa: E402
from mhqe.packs import DATA, PACK_NAMES, SLOT, EventPack, PackError, fit_record  # noqa: E402
from mhqe.quest import Quest, QuestFormatError, identity_rewrite    # noqa: E402

QUEST_DIR = os.environ.get("MHQE_QUEST_DIR")
PACK_DIR = os.environ.get("MHQE_PACK_DIR")
ARC = os.environ.get("MHQE_ARC")
CODE = os.environ.get("MHQE_CODE_BIN")


def rb(path):
    with open(path, "rb") as f:
        return f.read()


def loose():
    return sorted(glob.glob(os.path.join(QUEST_DIR, "q_*.quest")))


@unittest.skipUnless(QUEST_DIR, "MHQE_QUEST_DIR not set")
class LooseQuests(unittest.TestCase):
    def test_all_parse_and_roundtrip(self):
        files = loose()
        self.assertGreater(len(files), 100)
        for f in files:
            d = rb(f)
            self.assertEqual(identity_rewrite(d), d, f)
            q = Quest(d)
            self.assertEqual(q.get("quest_no"), int(os.path.basename(f)[2:7]))

    def test_rule_slot0_monster_has_stage_data(self):
        bad = []
        for f in loose():
            q = Quest(rb(f))
            mons = [m for m in q.monsters if m["Type"]]
            if mons and G.stage_ok(mons[0]["Type"], q.get("map")) is False:
                bad.append(os.path.basename(f))
        self.assertEqual(bad, [])


@unittest.skipUnless(PACK_DIR, "MHQE_PACK_DIR not set")
class Packs(unittest.TestCase):
    def packs(self):
        return [os.path.join(PACK_DIR, n) for n in PACK_NAMES if os.path.exists(os.path.join(PACK_DIR, n))]

    def test_untouched_pack_is_byte_identical(self):
        for p in self.packs():
            raw = rb(p)
            self.assertEqual(EventPack(p).to_bytes(), raw)

    def test_every_quest_roundtrips(self):
        for p in self.packs():
            for s in EventPack(p).slots:
                if s.quest is not None:
                    rec = s.raw[:DATA]
                    self.assertEqual(identity_rewrite(rec), rec)

    def test_edit_create_clear(self):
        p = self.packs()[0]
        raw = rb(p)
        pack = EventPack(p)
        q = pack.slots[0].quest
        q.set_text("name", "My Edited Quest")
        q.set("time_min", 35)
        pack.mark_dirty(0)
        free = EventPack(os.path.join(PACK_DIR, "quest3")) if os.path.exists(os.path.join(PACK_DIR, "quest3")) else None
        if free:
            tpl = pack.slots[3].quest
            nq = free.create_quest(0, tpl, 20900)
            nq.set_text("name", "Brand New Quest")
            out = free.to_bytes()
            self.assertEqual(len(out), len(rb(os.path.join(PACK_DIR, "quest3"))))
            again = EventPack("x", out)
            self.assertEqual(again.slots[0].filename, "q_20900.quest")
            self.assertEqual(again.slots[0].quest.get_text("name", 0), "Brand New Quest")
            self.assertEqual(again.slots[0].quest.get("quest_no"), 20900)
            self.assertTrue(all(s.empty for s in again.slots[1:]))
            free.clear_slot(0)
            self.assertEqual(free.to_bytes(), rb(os.path.join(PACK_DIR, "quest3")))
        out = pack.to_bytes()
        self.assertEqual(len(out), len(raw))
        again = EventPack("x", out)
        self.assertEqual(again.slots[0].quest.get_text("name", 0), "My Edited Quest")
        # all other slots are bit-identical to the original
        for i in range(1, 20):
            self.assertEqual(again.slots[i].serialize(), raw[4 + i * SLOT:4 + (i + 1) * SLOT])

    def test_oversize_text_is_rejected(self):
        pack = EventPack(self.packs()[0])
        q = pack.slots[0].quest
        q.set_text("description", "x" * 9000)
        with self.assertRaises(PackError):
            fit_record(q.to_bytes(), DATA)
        self.assertTrue(pack.validate_fit())


@unittest.skipUnless(ARC and QUEST_DIR, "MHQE_ARC / MHQE_QUEST_DIR not set")
class Arc(unittest.TestCase):
    def test_entries_match_loose_and_rebuild(self):
        raw = rb(ARC)
        a = arcmod.parse(raw)
        self.assertEqual(len(a.entries), 366)
        for e in a.entries:
            name = "quest.list" if e.leaf == "quest" else e.leaf + ".quest"
            self.assertEqual(rb(os.path.join(QUEST_DIR, name)), e.data, name)
        b = arcmod.parse(arcmod.build(a))
        self.assertEqual([(e.path, e.type_hash, e.flags, e.data) for e in a.entries],
                         [(e.path, e.type_hash, e.flags, e.data) for e in b.entries])
        rebuilt = arcmod.build(a)
        self.assertEqual(rebuilt[:12], raw[:12])
        self.assertEqual(struct.unpack_from("<I", rebuilt, 12 + 76)[0], 0x8000)


@unittest.skipUnless(CODE, "MHQE_CODE_BIN not set")
class CodeBin(unittest.TestCase):
    def test_nando_table_matches_game_code(self):
        c = rb(CODE)
        base = c.find(struct.pack("<8f", *G.NANDO_ROWS[0]) + struct.pack("<8f", *G.NANDO_ROWS[1]))
        self.assertGreater(base, 0)
        for i, row in enumerate(G.NANDO_ROWS):
            got = struct.unpack_from("<8f", c, base + 32 * i)
            for a, b in zip(got, row):
                self.assertAlmostEqual(a, b, places=4)


class Edits(unittest.TestCase):
    @unittest.skipUnless(QUEST_DIR, "MHQE_QUEST_DIR not set")
    def test_setters(self):
        q = Quest(rb(os.path.join(QUEST_DIR, "q_01302.quest")))
        before = len(q.data)
        q.set_text("name", "Short", langs=[0])
        q.set_text("description", "A much longer description than the original one.\r\nSecond line.")
        self.assertEqual(q.get_text("name", 0), "Short")
        self.assertNotEqual(len(q.data), before)
        self.assertEqual(q.get("quest_no"), 1302)
        q.set_monster(1, Type=2, Num=1)
        self.assertEqual(q.monsters[1]["Type"], 2)
        q.set_reward_table(1, [(5, 1, 100), (6, 2, 50)])
        self.assertEqual(q.reward1, [(5, 1, 100), (6, 2, 50)])
        q.set_reward_table(1, [(7, 3, 20)])
        self.assertEqual(q.reward1, [(7, 3, 20)])
        q.set_objective(1, 0x0001, 12, 2)
        self.assertEqual(q.objective(1), (1, q.objective(1)[1], 12, 2))
        with self.assertRaises(QuestFormatError):
            q.set("star", 999)
        with self.assertRaises(QuestFormatError):
            q.set_reward_table(1, [(1, 1, 1)] * 33)
        self.assertEqual(Quest(q.to_bytes()).get_text("name", 0), "Short")


class SupplyFiles(unittest.TestCase):
    SUPP_DIR = os.environ.get("MHQE_SUPP_DIR", "")

    def test_build_and_read(self):
        from mhqe import supp
        items = [(1, 1), (2, 99), (60, 5)]
        data = supp.build_supp(items)
        self.assertEqual(len(data), 472)
        self.assertEqual(supp.read_supp(data), items)

    def test_limits(self):
        from mhqe import supp
        with self.assertRaises(supp.SuppError):
            supp.build_supp([(1, 100)])
        with self.assertRaises(supp.SuppError):
            supp.build_supp([(i + 1, 1) for i in range(41)])

    @unittest.skipUnless(os.environ.get("MHQE_SUPP_DIR"), "MHQE_SUPP_DIR not set")
    def test_roundtrip_game_files(self):
        from mhqe import supp
        n = 0
        for f in glob.glob(os.path.join(self.SUPP_DIR, "supp*.supp")):
            items = supp.read_supp(rb(f))
            self.assertEqual(supp.read_supp(supp.build_supp(items)), items, f)
            n += 1
        self.assertGreater(n, 100)

    def test_custom_boxes(self):
        import tempfile
        from pathlib import Path
        from mhqe import supp
        with tempfile.TemporaryDirectory() as d:
            cb = supp.CustomBoxes(Path(d) / "c.json")
            no = cb.free_number(set())
            self.assertIn(no, supp.SPARE)
            cb.set_items(no, [(3, 4)])
            self.assertEqual(supp.CustomBoxes(Path(d) / "c.json").items(no), [(3, 4)])
            files = cb.export(Path(d) / "romfs")
            self.assertEqual(len(files), 1)
            self.assertEqual(supp.read_supp(files[0].read_bytes()), [(3, 4)])
            with self.assertRaises(supp.SuppError):
                cb.set_items(1, [(1, 1)])

    def test_box_names(self):
        import json
        import tempfile
        from pathlib import Path
        from mhqe import supp
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.json"
            cb = supp.CustomBoxes(path)
            a, b = supp.SPARE[0], supp.SPARE[1]
            cb.set_items(a, [(3, 4)])
            cb.set_items(b, [(5, 6)])
            self.assertEqual((cb.name(a), cb.name(b)), ("My box 1", "My box 2"))
            cb.set_name(a, "  Tracker   kit ")
            self.assertEqual(supp.CustomBoxes(path).name(a), "Tracker kit")
            with self.assertRaises(supp.SuppError):
                cb.set_name(b, "tracker KIT")          # names are unique
            with self.assertRaises(supp.SuppError):
                cb.set_name(b, "   ")
            cb.release(a)
            self.assertNotIn(a, supp.CustomBoxes(path).names)
            self.assertEqual(cb.default_name(), "My box 1")
            # a box file without names still loads
            path.write_text(json.dumps({"boxes": {str(a): [[3, 4]]}}), encoding="utf-8")
            self.assertEqual(supp.CustomBoxes(path).name(a), "My box 1")

    def test_installed_files(self):
        import tempfile
        from pathlib import Path
        from mhqe import supp
        with tempfile.TemporaryDirectory() as d:
            romfs = Path(d) / "romfs"
            cb = supp.CustomBoxes(Path(d) / "c.json")
            no = supp.SPARE[0]
            cb.set_items(no, [(3, 4)])
            self.assertEqual(supp.installed_files([romfs]), {})
            self.assertEqual(supp.file_state([], cb.items(no)), "missing")
            cb.export(romfs)
            found = supp.installed_files([romfs])
            self.assertEqual(list(found), [no])
            self.assertEqual(supp.file_state(found[no], cb.items(no)), "same")
            self.assertEqual(supp.file_state(found[no], [(3, 5)]), "older")


class GuideAndDefaults(unittest.TestCase):
    def test_guide_explains_every_setting(self):
        from mhqe import guide, helptext as H
        text = "\n".join(t for _tab, secs in guide.pages() for _h, t in secs)
        missing = [k for k, v in H.TEXT.items() if v and v not in text]
        self.assertEqual(missing, [], "settings with an (i) text that the guide does not explain")
        self.assertGreaterEqual(len(guide.pages()), 7)

    @unittest.skipUnless(QUEST_DIR, "MHQE_QUEST_DIR not set")
    def test_default_monster_uses_game_values(self):
        from mhqe import helptext as H
        for f in loose():
            q = Quest(rb(f))
            if q.get("star") != 4 or not any(m["Type"] for m in q.monsters):
                continue
            d = H.default_monster_values(q)
            key = H.group_key_for(q)
            self.assertIsNotNone(key)
            self.assertEqual((d["Nando_hp"], d["Nando_at"], d["Nando_etc"]), H.preset_rows(key))
            self.assertEqual(d["Size"], 100)
            break

    def test_pictures_are_shipped(self):
        from pathlib import Path
        from mhqe import icons
        a = Path(__file__).resolve().parent.parent / "assets"
        for n in ("items.png", "monsters_27.png", "monsters_54.png", "maps/map01_160.png", "app_icon.png"):
            self.assertTrue((a / n).is_file() and (a / n).stat().st_size > 1000, n)
        self.assertEqual(len(list((a / "maps").glob("map*_64.png"))), 15)

    def test_pictures_build(self):
        import tempfile
        from pathlib import Path
        from mhqe import artbuild
        romfs = os.environ.get("MHQE_ROMFS")
        code = os.environ.get("MHQE_CODE_BIN")
        if not romfs or not artbuild.pillow_available():
            self.skipTest("needs MHQE_ROMFS and Pillow")
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "data").mkdir()
            for name in ("items_en.json", "monsters.json"):
                (Path(d) / "data" / name).write_bytes((artbuild.ROOT / "data" / name).read_bytes())
            res = artbuild.build(romfs, d, code=code)
            self.assertGreater(res["monsters"], 80)
            self.assertGreaterEqual(res["maps"], 15)
            self.assertTrue((Path(d) / "assets" / "monsters_54.png").is_file())
            if code:
                self.assertGreater(res["items"], 1000)
        with self.assertRaises(artbuild.ArtError):
            artbuild.build(Path("/nonexistent"), tempfile.gettempdir())


class Tiers(unittest.TestCase):
    def test_labels(self):
        from mhqe import helptext as H
        self.assertEqual(H.tier_name(H.stat_tier("hp", 10)), "Low Rank")
        self.assertEqual(H.tier_name(H.stat_tier("hp", 42)), "G Rank")
        self.assertEqual(H.stat_tier("hp", 96), H.NIGHTMARE)
        self.assertEqual(H.stat_tier("at", 126), H.NIGHTMARE)
        self.assertEqual(H.stat_tier("etc", 127), H.NIGHTMARE)
        self.assertLessEqual(H.stat_tier("hp", 95), 3)

    def test_monotone(self):
        from mhqe import helptext as H
        for kind in ("hp", "at", "etc"):
            seq = [H.stat_tier(kind, r) for r in range(128)]
            self.assertEqual(seq, sorted(seq))


class Autofill(unittest.TestCase):
    def test_data(self):
        from mhqe import autofill
        self.assertTrue(autofill.available())
        r = autofill.small_monsters(0, "LR") or autofill.small_monsters(1, "LR")
        self.assertIsNotNone(r)
        self.assertIn("main_zako1", r[0])
        self.assertEqual(autofill.pool_for_star(1), "LR")
        self.assertEqual(autofill.pool_for_star(4), "HR")
        self.assertEqual(autofill.pool_for_star(7), "G")


@unittest.skipUnless(QUEST_DIR, "MHQE_QUEST_DIR not set")
class Waves(unittest.TestCase):
    def test_game_quests_follow_the_pattern_rule(self):
        """Objective = species of the last arrival group: checked on the game's multi-monster quests."""
        from mhqe import waves
        total = ok = 0
        for f in loose():
            q = Quest(rb(f))
            if len(waves.used_slots(q)) < 2 or q.objective(1)[0] not in waves.HUNT_TYPES:
                continue
            if waves.groups_of(q) is None:
                continue
            total += 1
            ok += waves.in_sync(q)
        self.assertGreater(total, 80)
        self.assertGreaterEqual(ok / total, 0.9, f"{ok}/{total}")

    def test_pattern_win_text(self):
        from mhqe import waves
        src = next(Quest(rb(f)) for f in loose()
                   if len(waves.used_slots(Quest(rb(f)))) == 3
                   and len({m["Type"] for m in Quest(rb(f)).monsters if m["Type"]}) == 3)
        for val, groups, _label, _game in waves.patterns_for(3):
            text = waves.pattern_win(src, groups)
            self.assertTrue(text.startswith("To win"), text)
            if len(groups) == 1:                          # everybody at the start: only two species can be targets
                self.assertIn("can stay alive", text)
                self.assertIn("#1", text.split("can stay alive")[0][-40:])
            if groups == (1, 1, 1):
                self.assertIn("all of them", text)
        self.assertEqual(waves.pattern_win(Quest(src.to_bytes()), (3,)).count("#"), 3)

    def test_patterns(self):
        from mhqe import waves
        self.assertEqual([v for v, *_ in waves.patterns_for(3)], [0, 1, 5, 6])
        self.assertEqual([v for v, *_ in waves.patterns_for(2)], [0, 1])
        self.assertEqual(waves.available_value(3, 8), 0)
        self.assertEqual(waves.available_value(4, 8), 8)


@unittest.skipUnless(PACK_DIR, "MHQE_PACK_DIR not set")
class SpawnsAndStrays(unittest.TestCase):
    def quests(self):
        for name in PACK_NAMES:
            p = os.path.join(PACK_DIR, name)
            if os.path.exists(p):
                for s in EventPack(p).used_slots():
                    yield s.quest

    def test_spawn_edit_roundtrip(self):
        from mhqe import spawns
        q = next(x for x in self.quests() if spawns.readable(x) and len(spawns.species(x)) >= 2)
        raw = q.to_bytes()
        recs = spawns.records(q)
        spawns.write(q, recs)
        self.assertEqual(q.to_bytes(), raw, "rewriting the same list is byte-identical")
        em = next(iter(spawns.species(q)))
        n = spawns.species(q)[em]
        spawns.remove(q, em)
        self.assertNotIn(em, spawns.species(q))
        self.assertEqual(len(q.to_bytes()), len(raw))
        spawns.change(q, next(iter(spawns.species(q))), em)
        self.assertEqual(sum(spawns.species(q).values()), len(recs) - n)

    def test_base_quest_gets_the_game_list(self):
        from mhqe import autofill, spawns
        from mhqe.project import RomSource
        romfs = os.environ.get("MHQE_ROMFS")
        if not romfs:
            self.skipTest("MHQE_ROMFS not set")
        base = RomSource(romfs, load_edits=False).quests
        donors = list(self.quests())
        made = 0
        for no, tpl in sorted(base.items()):
            q = tpl.copy()
            q.pad_to(DATA)
            if not spawns.is_bare(q):
                continue
            if spawns.adopt_game_list(q, no, q.get("star"), autofill.pool_for_star(q.get("star")), donors):
                self.assertGreater(len(spawns.records(q)), 0)
                made += 1
            fit_record(q.to_bytes(), DATA)
        self.assertGreater(made, 250)

    def test_unstable_means_roaming_chance(self):
        from mhqe import strays
        for q in self.quests():
            self.assertEqual(strays.is_unstable(q), q.get("nora_set_per") > 0)
        q = next(x for x in self.quests() if strays.is_unstable(x))
        strays.make_stable(q)
        self.assertFalse(strays.is_unstable(q))
        refs = strays.references(q.get("map"), q.get("star"))
        if refs:
            strays.apply(q, refs[0])
            self.assertTrue(strays.is_unstable(q))
            self.assertEqual(strays.reference_of(q)["table"], q.get("nora_set_table"))


class RewardPlan(unittest.TestCase):
    def test_every_monster_is_represented(self):
        """The three monsters of the user's quest (Savage Deviljho, Azure Rathalos, Barroth) each get materials."""
        from mhqe import autofill
        names = {n: e for e, n in G.MONSTERS.items()}
        want = [names["Savage Deviljho"], names["Azure Rathalos"], names["Barroth"]]

        class Fake:
            monsters = [{"Type": e} for e in want] + [{"Type": 0}] * 2

            def get(self, k):
                return {"map": 1, "star": 8}[k]
        for pool in ("HR", "G"):
            rows, _rows2, text = autofill.reward_plan(Fake(), pool)
            owned = set()
            for item, _qty, _ch in rows:
                owned |= autofill.owners_of(item)
            for e in want:
                self.assertIn(e, owned, f"{G.mon_name(e)} has no material at {pool}")
            self.assertTrue(any(not autofill.owners_of(i) for i, _q, _c in rows), "other items present")

    def test_shared_materials(self):
        from mhqe import autofill
        names = {n: e for e, n in G.MONSTERS.items()}
        both = [i for i in range(len(G.ITEMS)) if {names["Deviljho"], names["Savage Deviljho"]} <= autofill.owners_of(i)]
        self.assertGreaterEqual(len(both), 3)


if __name__ == "__main__":
    unittest.main()
