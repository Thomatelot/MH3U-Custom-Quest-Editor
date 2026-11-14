"""Tests for the phone notebook's drafts (mhqe/phone.py) and its data file (android/web/data.js).
The draft-to-quest tests need MHQE_ROMFS (romfs folder of the game)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mhqe import gamedata as G, phone, rules, waves  # noqa: E402
from mhqe import helptext as H  # noqa: E402
from mhqe.project import RomSource  # noqa: E402
from mhqe.quest import Quest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ROMFS = os.environ.get("MHQE_ROMFS")


def draft(**kw):
    d = {"format": phone.FORMAT, "version": 1, "name": "Phone quest", "client": "Me", "description": "Line 1\nLine 2",
         "objective_text": "", "sub_objective": "", "failure": "", "star": 4, "hub": "Port", "rank": 3, "map": 1,
         "time": 50, "fee": 900, "reward": 9000, "hrp": 600, "hr": None, "players": 4, "naked": False, "night": False,
         "arena_carves": False, "monsters": [{"em": 1, "count": 1, "size": 100, "strength": None}], "arrival": 0,
         "objective": {"kind": "hunt", "item": 0, "em": 0, "count": 1}, "rewards": {"auto": True, "items": []}}
    d.update(kw)
    return d


class Drafts(unittest.TestCase):
    def test_clean_puts_values_in_range(self):
        d = phone.clean(draft(star=40, time=500, hr=42, players=7, monsters=[{"em": 9999}, {"em": 2, "count": 500}],
                              objective={"kind": "dance"}, rewards={"auto": False, "items": [{"item": 0}]}))
        self.assertEqual((d["star"], d["time"], d["hr"], d["players"]), (10, 99, None, 4))
        self.assertEqual(d["monsters"], [{"em": 2, "count": 99, "size": 100, "strength": None}])
        self.assertEqual(d["objective"]["kind"], "hunt")
        self.assertTrue(d["rewards"]["auto"])           # no usable item: automatic

    def test_not_a_draft(self):
        with self.assertRaises(phone.DraftError):
            phone.clean({"format": "something else"})
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.mh3ud"
            p.write_text("not json", encoding="utf-8")
            with self.assertRaises(phone.DraftError):
                phone.read_file(p)

    def test_backup_file_holds_several(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "all.mh3ud"
            p.write_text(json.dumps({"format": phone.BUNDLE, "drafts": [draft(name="A"), draft(name="B")]}), encoding="utf-8")
            self.assertEqual([d["name"] for d in phone.read_file(p)], ["A", "B"])

    def test_phone_data_matches_the_editor(self):
        text = (ROOT / "android" / "web" / "data.js").read_text(encoding="utf-8")
        data = json.loads(text[text.index("{"):text.rindex("}") + 1])
        self.assertEqual({m["id"] for m in data["monsters"]}, set(G.MONSTERS))
        self.assertEqual({g["key"] for g in data["groups"]}, set(H.GROUPS))
        self.assertEqual(sorted(data["day_only_maps"]), sorted(rules.DAY_ONLY_MAPS))
        for m in data["monsters"]:
            self.assertEqual(m["maps"], G.maps_for_monster(m["id"]))


@unittest.skipUnless(ROMFS, "MHQE_ROMFS not set")
class DraftToQuest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rom = RomSource(ROMFS, workspace=Path(tempfile.mkdtemp()), load_edits=False)
        cls.cands = [(q.get_text("name", 0), q, "Game quests") for _no, q in sorted(rom.quests.items())]

    def make(self, d):
        d = phone.clean(d)
        label, tpl, cat = phone.best_template(d, self.cands)
        self.assertEqual(tpl.get("map"), d["map"])
        q = tpl.copy()
        notes = phone.apply(q, d, source_no=tpl.get("quest_no"))
        return Quest(q.to_bytes()), notes

    def test_hunt(self):
        q, _notes = self.make(draft(night=True, hr=4, players=2))
        for lang in range(5):
            self.assertEqual(q.get_text("name", lang), "Phone quest")
        self.assertEqual(q.get_text("description", 1), "Line 1\r\nLine 2")
        self.assertEqual(q.get_text("objective", 0), "Hunt a Rathian")
        self.assertEqual((q.get("star"), q.get("prog_no"), q.get("map")), (4, 3, 1))
        self.assertEqual((q.get("contract"), q.get("reward_money"), q.get("penalty"), q.get("main_hrp")),
                         (900, 9000, 3000, 600))
        self.assertTrue(rules.is_night(q))
        self.assertEqual(rules.rules_of(q.get("special_cond"), q.get("special_cond2")), rules.Req(4, 2, False))
        mons = [m for m in q.monsters if m["Type"]]
        self.assertEqual([m["Type"] for m in mons], [1])
        self.assertEqual(q.objective(1)[:1] + q.objective(1)[2:], (1, 1, 1))
        self.assertTrue(q.reward1)                    # automatic rewards

    def test_copies_become_cards(self):
        d = draft(map=5, star=7, rank=4, monsters=[{"em": 2, "count": 2, "size": 125, "strength": "Port 8"},
                                                    {"em": 74, "count": 1}], arrival=1,
                  objective={"kind": "capture"}, rewards={"auto": False, "items": [{"item": 10, "qty": 2, "chance": 100}]})
        q, _notes = self.make(d)
        mons = [m for m in q.monsters if m["Type"]]
        self.assertEqual([(m["Type"], m["Num"]) for m in mons], [(2, 1), (2, 1), (74, 1)])
        self.assertEqual(mons[0]["Size"], 125)
        self.assertEqual(mons[0]["Nando_hp"], H.preset_rows("Port 8")[0])
        self.assertNotEqual(mons[0]["Starttype"], mons[1]["Starttype"])   # copies start apart
        self.assertEqual(q.objective(1)[0], 0x0081)
        self.assertTrue(waves.in_sync(q))
        self.assertEqual(q.reward1, [(10, 2, 100)])
        self.assertEqual(q.reward2, [])

    def test_delivery_and_three_rules(self):
        q, notes = self.make(draft(objective={"kind": "deliver", "item": 10, "count": 3}, monsters=[],
                                   hr=5, players=2, naked=True))
        self.assertEqual(q.objective(1)[:1] + q.objective(1)[2:], (2, 10, 3))
        self.assertEqual(q.get("clr_pattern"), 0)
        self.assertFalse(any(m["Type"] for m in q.monsters))
        self.assertTrue(any("two rules" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
