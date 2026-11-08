"""Text of the built-in Guide (one tab per topic) and of docs/GUIDE.md (same text, see tools/build_guide_md.py).

Every setting of the editor is explained here. Numbers quoted from the game come from helptext.py, which
reads them from the game's own quests (data/benchmarks.json): nothing below is an invented example.
"""
from __future__ import annotations

from . import helptext as H

CITRA_USER = "C:\\Users\\<you>\\AppData\\Roaming\\Citra"
SAVE_DIR = "sdmc\\Nintendo 3DS\\<id0>\\<id1>\\extdata\\00000000\\00000B1D\\user"


def pages() -> list[tuple[str, list[tuple[str, str]]]]:
    """[(tab title, [(heading, text), ...]), ...]"""
    return [
        ("Getting started", _start()),
        ("General tab", _general()),
        ("Monsters tab", _monsters()),
        ("Supply Box", _supply()),
        ("Rewards and Text", _rewards_text()),
        ("Game values", _values()),
        ("Files and backups", _files()),
        ("Tested or not", _limits()),
    ]


def _start():
    return [
        ("What this editor does", (
            "It creates and edits quests for Monster Hunter 3 Ultimate (3DS, European version) on Citra or on a real "
            "3DS. Custom quests are written into the game's event-quest slots (3 packs of 20 quests, plus the pack of "
            "challenge quests), where the game lists them like its own event quests. It can also edit the game's own "
            "Village and Port quests as a mod folder (the ROM is never changed)."
        )),
        ("Make a custom event quest", (
            "1. Close Citra (it rewrites the quest files when it exits).\n"
            "2. In-game quests > Event quests: select a free slot and press 'New quest here...'.\n"
            "3. Pick a quest to copy - preferably one on the same map, with similar monsters - and give it a name.\n"
            "4. Edit the tabs: General, Monsters, Supply Box, Rewards, Text.\n"
            "5. Press Save (Ctrl+S). A full backup is made first.\n"
            "6. Start the game: the quest is in the event quest list.\n\n"
            "Why copy a quest on the same map? The end of a quest file holds data that depends on the map (the places "
            "of the small monsters, a block that is not understood). A copy keeps it consistent."
        )),
        ("Event quests or challenge quests", H.tip("challenge")),
        ("The four pages", (
            "In-game quests: the quest files of your save. Tabs: Event quests (packs 1-3, where custom quests go), "
            "Challenge quests (pack 4) and Backups. Actions: Edit, New quest here, Put a quest here (from the library, "
            "a file or a backup), Duplicate, To library, Export, Clear slot.\n\n"
            "Quest library: quests kept on your PC (library/*.mh3uq). Edit them, share the files, and send them into a "
            "game slot with 'To game'.\n\n"
            "Base game: optional. The game's own Village and Port quests, saved as a Citra mod. Needs the extracted "
            "romfs folder. Install the mod into Citra with the button on that page; on a real 3DS copy the output folder "
            "into luma/titles/00040000000B1D00/romfs.\n\n"
            "Guide: this page."
        )),
        ("Keys, themes, developer mode", (
            "Ctrl+S saves. Ctrl+F searches the tab you are looking at (labels, values, list rows and the (i) texts); on a "
            "quest list it jumps to the search box. All text can be selected and copied. 'Undo changes' puts the quest "
            "back as it was when you opened it. The checks badge in the top bar warns about mistakes that can stop a "
            "quest from loading.\n\n"
            "Themes: Moga Parchment (light, default) and Tanzia Night (dark), in Settings.\n\n"
            + H.tip("dev_mode")
        )),
        ("Pictures", (
            "The monster, item and map pictures come with the editor (folder assets). If they are missing, or you want "
            "them rebuilt from your own extracted game, use Settings > 'Rebuild the pictures from my game...' (a few "
            "seconds; needs the Pillow package, 'py -m pip install pillow'; item icons also need the game's "
            "exefs/code.bin). Without pictures everything works, with empty pictures."
        )),
        ("Real 3DS", (
            "Back up the game's extra data with Checkpoint (or JKSM), copy it to your PC, choose that folder (In-game "
            "quests > Change folder...), edit and save, then restore it to the 3DS with Checkpoint. Custom supply boxes "
            "and base-game edits are romfs mods: copy their output folder into luma/titles/00040000000B1D00/romfs."
        )),
    ]


def _general():
    return [
        ("Star rank", H.tip("star")),
        ("Map", H.tip("map")),
        ("Time limit", H.tip("time_min") + "\n\nThe 'Frozen clock' box sets 99 minutes, the lowest frozen value."),
        ("Fee, Reward, Penalty", (
            "Fee: " + H.tip("contract") + "\nReward: " + H.tip("reward_money") + "\nPenalty: " + H.tip("penalty")
            + "\n\nThe (i) next to each shows what the game's quests of the same star rank use."
        )),
        ("HR points", "HR points: " + H.tip("main_hrp") + "\nHR points on failure: " + H.tip("failure_hrp")),
        ("Objectives: pattern", H.tip("clr_pattern")),
        ("Objectives: type, target, how it is counted, count", (
            H.tip("objective") + "\n\nTarget: " + H.tip("species") + "\n\nCount: " + H.tip("obj_count")
            + "\n\n'Set the objectives from the monsters' writes objectives A and B the way the game's multi-monster "
            "quests do. The Monsters tab does it for you whenever you add, remove, replace or reorder a monster."
        )),
        ("Environment: Stable or Unstable", (
            H.ENV_TIP + "\n\nChance of roaming monsters: " + H.tip("nora_set_per")
            + "\nAt most at the same time: " + H.tip("nora_set_max")
            + "\n'Roaming monsters like another game quest...' copies the roaming settings of a game quest on the same "
            "zone. Changing the map offers to replace the small monsters and the roaming settings with the new map's."
        )),
        ("Developer mode: other gameplay settings", (
            "Arrival pattern (start_param): " + H.tip("start_param") + "\n\n"
            "Gathering table (hagi_no): " + H.tip("hagi_no") + "\n\n"
            "Progress level (prog_no): " + H.tip("prog_no") + "\n\n"
            "Monster level (enemy_lv): " + H.tip("enemy_lv") + "\n\n"
            "Special flag: " + H.tip("special_flag") + "\n\n"
            "Special condition: " + H.tip("special_cond") + "\n\n"
            "Special condition 2: " + H.tip("special_cond2") + "\n\n"
            "Cutscene (demo_no): " + H.tip("demo_no") + "\n\n"
            "Roaming list settings: use roaming list (" + H.tip("nora_set_type") + ") / second % ("
            + H.tip("nora_per_type") + ") / list number (" + H.tip("nora_set_table") + ") / always comes ("
            + H.tip("nora_pekko") + ")\n\n"
            "Quest number: " + H.tip("quest_no")
        )),
        ("Developer mode: Advanced tab", (
            "Category flags: " + H.tip("category") + "\n\nThe tab also lists every numeric field of the quest "
            "(double-click to edit) and the hidden data at the end of the quest, which is kept as it is. "
            "Internal pointer: " + H.tip("zako_ptr")
        )),
    ]


def _monsters():
    return [
        ("Large monsters: the cards", (
            "Each large monster has a card, numbered #1, #2, #3 in the order they are read. Change... picks another "
            "species. Copy from a quest... copies a monster with every setting from another quest: it is the safest way "
            "to get a working monster. Remove takes it out of the quest. The arrows ◀ ▶ reorder the cards. A monster "
            "needs spawn data on the quest's map, otherwise the game can crash when the quest loads: the card says "
            "'Appears on <map>' or warns you. Up to 5 large monsters fit in a quest."
        )),
        ("Size % and Size like", H.tip("Size") + "\n\n" + H.SIZE_TIP),
        ("Strength like, Health, Attack, Toughness", (
            "'Strength like' sets Health, Attack and Toughness (and the hidden stamina and size spread) to the typical "
            "values of the game's own quests of that hub and star rank.\n\n"
            "Health: " + H.TEXT["Nando_hp"] + "\nAttack: " + H.TEXT["Nando_at"] + "\nToughness: " + H.TEXT["Nando_etc"]
            + "\n\nThe line under each slider gives the real multiplier and the rank it matches. Above the hardest row "
            "that any game quest uses, the label is Nightmare: harder than anything in the game."
        )),
        ("Count", H.tip("Num") + " (Shown only when the quest has a single large monster, or in developer mode.)"),
        ("How the monsters arrive", H.ARRIVAL_TIP + "\n\n" + H.ARRIVAL_NOTE),
        ("Small monsters", (
            H.SPAWN_TIP + "\n\nAdd a species, Change..., Remove: edit the list. 'Fill from zone and rank...': "
            + H.SPAWN_FILL_TIP + "\n\nStrength of all small monsters: " + H.tip("zako_rows")
        )),
        ("Developer mode: per-monster details", (
            "Stamina: " + H.tip("Stamina") + "\n\n"
            "Start type: " + H.tip("Starttype") + "\n\n"
            "Size spread: " + H.tip("Sizeparam") + "\n\n"
            "Set type: " + H.tip("Settype") + "\n\n"
            "Nando2: " + H.tip("Nando2") + "\n\n"
            "Main small-monster species: " + H.tip("main_zako1") + " " + H.tip("main_zako2")
        )),
    ]


def _supply():
    return [
        ("The supply box", H.tip("item_set_no") + "\n\n'Choose another supply box...' lists the game's boxes; search "
         "for an item to find the boxes that contain it. 'Fill from zone and rank...' picks the box that the game's "
         "quests use on this zone at the chosen rank."),
        ("Your own box", (
            "'Make my own box' copies the current box into a box of yours, where you choose every item (up to 40 "
            "different items, 99 of each) and give it a name. A quest does not contain its box, only a number: the "
            "editor uses one of the 10 box numbers that no game quest uses, and writes your items into a supply file "
            "for that number.\n\n"
            "The files must be installed: the 'Install the supply files into Citra' button copies them into Citra's "
            "load/mods folder; on a real 3DS copy output/MH3U_Supply_Mod/romfs into luma/titles/00040000000B1D00/romfs. "
            "Without the files the game opens the box it normally has under that number. Every player of a "
            "multiplayer quest needs the same files."
        )),
        ("My supply boxes (manager)", (
            "The 'Supply boxes' button at the top (also 'My supply boxes...' in the Supply Box tab) opens the manager: "
            "rename a box, edit its items, see which quests use it and whether it is installed in Citra, install it, "
            "remove its file from Citra, or delete the box. Deleting a box also removes its file from Citra, after "
            "listing the quests that use it (they will open the game's own box with that number). Boxes are kept "
            "until you delete them; there is room for 10."
        )),
        ("Developer mode: second supply delivery", (
            "Delivery set: " + H.tip("supp_set_no") + "\n\nTime condition: " + H.tip("supp_time_flag")
            + "\n\nMonster condition: " + H.tip("supp_enemy_type") + "\n\nCount: " + H.tip("supp_enemy_num")
        )),
    ]


def _rewards_text():
    return [
        ("Reward tables A and B", H.tip("rewards") + "\n\nAdd..., Edit..., Remove and ▲ ▼ edit a table (up to 32 lines). "
         "The total chance of a table is shown under it."),
        ("Fill from the quest's monsters and rank", (
            "Builds table A from the game's own quests: the materials of each large monster of the quest, then the "
            "other items the game gives at that rank and zone (armor spheres, charms, ores, bones, bugs...). Each item "
            "belongs to the few monsters whose quests give it, so shared materials go to the right monsters. The dialog "
            "says what it is based on. Everything stays editable."
        )),
        ("Text tab", (
            "The game stores every text in English, French, German, Italian and Spanish; the console language decides "
            "which one you see. Quest name, Objective text, Sub-objective, Failure conditions, Client and Description "
            "are edited per language; 'Copy this language to the 4 others' fills the other languages with the current "
            "one."
        )),
    ]


def _values():
    return [
        ("Rank labels of the Health / Attack / Toughness rows", H.tier_table()),
        ("Health multipliers by star rank", H.table("hp")),
        ("Attack multipliers by star rank", H.table("atk")),
        ("Damage taken by star rank", H.table("dmg")),
        ("Where these numbers come from", (
            "They are medians measured on the game's own quests (365 quests of the base game plus the event and "
            "challenge quests). Health, Attack and Toughness are rows (0-127) of the game's 128-row difficulty table, "
            "not percentages: the editor shows the multiplier of the row and the rank it matches. A table with the "
            "typical fee, reward and HR points of each hub and star rank is at the bottom of this page in the editor."
        )),
    ]


def _files():
    return [
        ("What the editor changes", (
            "1. Your save's quest files: quest1, quest2, quest3 (event quests) and quest4 (challenge quests), in\n"
            f"   {CITRA_USER}\\{SAVE_DIR}\n"
            "   (the exact folder is found automatically). This is the only game data written by an ordinary save.\n"
            "2. Optional mods, written in the editor's own output folder and copied into Citra on request:\n"
            "   output/MH3U_Supply_Mod/romfs (your own supply boxes) and output/MH3U_Quest_Mod/romfs (edited base-game "
            "quests), installed into <Citra>/load/mods/00040000000B1D00/romfs.\n"
            "3. Files next to the program: settings.json, custom_supply.json, backups/, library/, error_log.txt (only "
            "if something went wrong)."
        )),
        ("What to back up yourself", (
            "Before the first save, copy your save's extra data folder (the 'user' folder above holding quest1-quest4) "
            "and, if you use mods, the folder <Citra>/load/mods/00040000000B1D00. On a real 3DS, back up the save with "
            "Checkpoint or JKSM. The editor makes its own backups too, but a copy you made yourself is the one that "
            "cannot be touched by a bug."
        )),
        ("The editor's backups", (
            "Every save first makes a full backup of quest1..quest4 (backups/full/) and keeps a separate copy of every "
            "quest it replaces, edits or clears (backups/quests/), so a single quest can be put back in its slot. "
            "backups/original/ keeps the very first version of each file and is never deleted. Restoring a backup backs "
            "up the current files first. Everything is listed in In-game quests > Backups."
        )),
        ("Good habits", (
            "Close Citra before saving. Test on Citra before a real 3DS. Keep one slot per experiment. Share quests as "
            ".mh3uq files from the library rather than the raw save files."
        )),
    ]


def _limits():
    return [
        ("Confirmed in the game", (
            "Arrival patterns: 'one after another', 'the first, then the other two together' and 'the first two "
            "together, then the last' work as described; with 'all at the start' every monster is in the zone from the "
            "beginning and the quest ends when the target monsters are slain.\n"
            "Time limit: up to 98 minutes the clock counts down; from 99 minutes it is frozen.\n"
            "Environment: Unstable is shown on the quest board when the chance of roaming monsters is above 0."
        )),
        ("Read from the game's files, not seen in play", (
            "The meaning of most quest fields comes from comparing the game's own quests (the (i) texts say 'not "
            "confirmed' where that is all there is). Not every pattern that the editor allows appears in the game: "
            "the three-monsters-at-once pattern and the five-monster 'one after the other' follow the same rule but "
            "never appear in a game quest, so test them."
        )),
        ("Known limits", (
            "The monsters that roam an Unstable zone cannot be chosen: their list is stored in the game, not in the "
            "quest. There is no 'enraged' or 'charged' setting in the quest file: the game's 'Clashing Fists!' and "
            "'Descent into Hades' use King Size monsters. Only the European version (title id 00040000000B1D00) was "
            "studied. The block at the end of an event quest that is not understood is kept unchanged."
        )),
        ("Not tested yet", (
            "The editor was tested on Windows with Citra only. A real 3DS (the files are the same, but nobody has tried "
            "on hardware yet), other regions, Linux and macOS are untested: this is a first version, so you may be the "
            "first to find out. Please report what you find."
        )),
    ]
