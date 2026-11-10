"""Text of the built-in Guide (one tab per topic) and of docs/GUIDE.md (same text, see tools/build_guide_md.py).

Every setting of the editor is explained here. Numbers quoted from the game come from helptext.py, which
reads them from the game's own quests (data/benchmarks.json): nothing below is an invented example.
"""
from __future__ import annotations

from . import helptext as H
from .i18n import _


CITRA_USER = "C:\\Users\\<you>\\AppData\\Roaming\\Citra"
SAVE_DIR = "sdmc\\Nintendo 3DS\\<id0>\\<id1>\\extdata\\00000000\\<00000B1D (EU) or 00000AE4 (US)>\\user"
TITLES = "00040000000B1D00 (EU) or 00040000000AE400 (US)"


def pages() -> list[tuple[str, list[tuple[str, str]]]]:
    """[(tab title, [(heading, text), ...]), ...]"""
    return [
        ("Getting started", _start()),
        ("General tab", _general()),
        ("Monsters tab", _monsters()),
        ("Supply Box", _supply()),
        ("Rewards and Text", _rewards_text()),
        ("Game values", _values()),
        ("Monster pack", _pack()),
        ("Files and backups", _files()),
        ("Tested or not", _limits()),
    ]


def _start():
    return [
        ("What this editor does", (
            _("It creates and edits quests for Monster Hunter 3 Ultimate (3DS, European or North American version; choose "
            "yours in Settings > Game version) on Citra or on a real "
            "3DS. Custom quests are written into the game's event-quest slots (3 packs of 20 quests, plus the pack of "
            "challenge quests), where the game lists them like its own event quests. It can also edit the game's own "
            "Village and Port quests as a mod folder (the ROM is never changed).")
        )),
        ("Make a custom event quest", (
            _("1. Close Citra (it rewrites the quest files when it exits).\n"
            "2. In-game quests > Event quests: select a free slot and press 'New quest here...'.\n"
            "3. Pick a quest to copy - preferably one on the same map, with similar monsters - and give it a name.\n"
            "4. Edit the tabs: General, Monsters, Supply Box, Rewards, Text.\n"
            "5. Press Save (Ctrl+S). A full backup is made first.\n"
            "6. Start the game: the quest is in the event quest list.\n\n"
            "Why copy a quest on the same map? The end of a quest file holds data that depends on the map (the places "
            "of the small monsters, a block that is not understood). A copy keeps it consistent.")
        )),
        ("Event quests or challenge quests", _(H.tip("challenge"))),
        ("The five pages", (
            _("In-game quests: the quest files of your save. Tabs: Event quests (packs 1-3, where custom quests go), "
            "Challenge quests (pack 4) and Backups. Actions: Edit, New quest here, Put a quest here (from the library, "
            "a file or a backup), Duplicate, To library, Export, Clear slot.\n\n"
            "Quest library: quests kept on your PC (library/*.mh3uq). Edit them, share the files, and send them into a "
            "game slot with 'To game'.\n\n"
            "Base game: optional. The game's own Village and Port quests, saved as a Citra mod. Needs the extracted "
            "romfs folder. Install the mod into Citra with the button on that page; on a real 3DS copy the output folder "
            "into luma/titles/<title id>/romfs.\n\n"
            "Monster pack: optional ROM hack that lets large monsters start on maps the game does not allow "
            "(see its own tab in this Guide).\n\n"
            "Guide: this page.")
        )),
        ("Keys, themes, developer mode", (
            _("Ctrl+S saves. Ctrl+F searches the tab you are looking at (labels, values, list rows and the (i) texts); on a "
            "quest list it jumps to the search box. All text can be selected and copied. 'Undo changes' puts the quest "
            "back as it was when you opened it. The checks badge in the top bar warns about mistakes that can stop a "
            "quest from loading.\n\n"
            "Themes: Moga Parchment (light, default) and Tanzia Night (dark), in Settings.\n\n"
            "Language: English or French (Settings > Language / Langue). In French, item, monster and map names "
            "are the game's own French names. The quests themselves keep their texts in the game's five "
            "languages (Text tab).\n\n")
            + _(H.tip("dev_mode"))
        )),
        ("Choosing monsters and items", (
            _("The monster list is grouped by class (Bird Wyverns, Flying Wyverns, Brute Wyverns...) with the easiest "
            "monsters first; the stars under each name say how hard players usually find it (an editorial guide from 1 "
            "to 5 stars, not a game value: the quest's Health and Attack rows decide its real strength). 'By "
            "difficulty' lists them from Beginner to Hardest instead. The item list (rewards, supply boxes, "
            "deliveries) is grouped in families that follow the game's own icons: healing, food and bait, bombs and "
            "traps, tools, ammo, plants, bugs, ores, fish, monster parts, rare parts and gems, eggs, coins and "
            "tickets, jewels. Search looks through everything (in French, the English names work too).")
        )),
        ("Pictures", (
            _("The monster, item and map pictures come with the editor (folder assets). If they are missing, or you want "
            "them rebuilt from your own extracted game, use Settings > 'Rebuild the pictures from my game...' (a few "
            "seconds; needs the Pillow package, 'py -m pip install pillow'; item icons also need the game's "
            "exefs/code.bin). Without pictures everything works, with empty pictures.")
        )),
        ("Real 3DS", (
            _("Back up the game's extra data with Checkpoint (or JKSM), copy it to your PC, choose that folder (In-game "
            "quests > Change folder...), edit and save, then restore it to the 3DS with Checkpoint. Custom supply boxes "
            "and base-game edits are romfs mods: copy their output folder into luma/titles/<title id>/romfs. Title id: ")
            + TITLES + _(".")
        )),
    ]


def _general():
    return [
        ("Star rank", _(H.tip("star"))),
        ("Map", _(H.tip("map"))),
        ("Hunters start", _(H.tip("supp_enemy_num")) + _("\n\nThe line under the list gives the odds for the quest's "
         "map, with the area numbers of the in-game map.")),
        ("Time limit", _(H.tip("time_min")) + _("\n\nThe 'Frozen clock' box sets 99 minutes, the lowest frozen value.")),
        ("Who can join, day or night", (
            _(H.REQ_TIP) + _("\n\nTime of day: ") + _(H.DAYNIGHT_TIP)
        )),
        ("Fee, Reward, Penalty", (
            _("Fee: ") + _(H.tip("contract")) + _("\nReward: ") + _(H.tip("reward_money")) + _("\nPenalty: ") + _(H.tip("penalty"))
            + _("\n\nThe (i) next to each shows what the game's quests of the same star rank use.")
        )),
        ("HR points", _("HR points: ") + _(H.tip("main_hrp")) + _("\nHR points on failure: ") + _(H.tip("failure_hrp"))),
        ("Objectives: pattern", _(H.tip("clr_pattern"))),
        ("Objectives: type, target, how it is counted, count", (
            _(H.tip("objective")) + _("\n\nTarget: ") + _(H.tip("species")) + _("\n\nCount: ") + _(H.tip("obj_count"))
            + _("\n\n'Set the objectives from the monsters' writes objectives A and B the way the game's multi-monster "
            "quests do. The Monsters tab does it for you whenever you add, remove, replace or reorder a monster.")
        )),
        ("Environment: Stable or Unstable", (
            _(H.ENV_TIP) + _("\n\nChance of roaming monsters: ") + _(H.tip("nora_set_per"))
            + _("\nAt most at the same time: ") + _(H.tip("nora_set_max"))
            + _("\n'Roaming monsters like another game quest...' copies the roaming settings of a game quest on the same "
            "zone. Changing the map offers to replace the small monsters and the roaming settings with the new map's.")
        )),
        ("Developer mode: other gameplay settings", (
            _("Arrival pattern (start_param): ") + _(H.tip("start_param")) + _("\n\n"
            "Supply rank / story step (hagi_no): ") + _(H.tip("hagi_no")) + _("\n\n"
            "Monster rank (prog_no): ") + _(H.tip("prog_no")) + _("\n\n"
            "Intro cutscene (enemy_lv): ") + _(H.tip("enemy_lv")) + _("\n\n"
            "Special flag: ") + _(H.tip("special_flag")) + _("\n\n"
            "Special condition: ") + _(H.tip("special_cond")) + _("\n\n"
            "Special condition 2: ") + _(H.tip("special_cond2")) + _("\n\n"
            "Unused (demo_no): ") + _(H.tip("demo_no")) + _("\n\n"
            "Rannyu_limite (ren_pattern): ") + _(H.tip("ren_pattern")) + _("\n\n"
            "Field names: this part of the quest record was named one field off in version 1.1 and older; the "
            "labels now follow the names of the game's own reader (found by mh3u-quest-studio and checked against "
            "every 3DS quest). Only the labels changed: quests made before keep exactly the same bytes.\n\n"
            "Roaming list settings: use roaming list (") + _(H.tip("nora_set_type")) + _(") / second % (")
            + _(H.tip("nora_per_type")) + _(") / list number (") + _(H.tip("nora_set_table")) + _(") / always comes (")
            + _(H.tip("nora_pekko")) + _(")\n\n"
            "Quest number: ") + _(H.tip("quest_no"))
        )),
        ("Developer mode: Advanced tab", (
            _("Category flags: ") + _(H.tip("category")) + _("\n\nThe tab also lists every numeric field of the quest "
            "(double-click to edit) and the hidden data at the end of the quest, which is kept as it is. "
            "Internal pointer: ") + _(H.tip("zako_ptr"))
        )),
    ]


def _monsters():
    return [
        ("Large monsters: the cards", (
            _("Each large monster has a card, numbered #1, #2, #3 in the order they are read. Change... picks another "
            "species. Copy from a quest... copies a monster with every setting from another quest: it is the safest way "
            "to get a working monster. Remove takes it out of the quest. The arrows ◀ ▶ reorder the cards. The game "
            "lets each monster start only on some maps; on any other map it skips the monster, which then never appears "
            "(tested in the game). The card says 'Appears on <map>' or warns you; the Monster pack page can add the "
            "missing maps. Up to 5 large monsters fit in a quest.")
        )),
        ("Starts in: where a monster starts", (
            _(H.tip("Starttype")) + _("\n\nThe list shows the area numbers painted on the in-game map (the game's own "
            "numbering of the areas is different: e.g. Rathian's usual start on the Deserted Island is the area the map "
            "shows as 8). Copies of one species are spread over different start points automatically.\n\n"
            "The small map on the card shows where the monster starts, in yellow. Click it (or Map...) for the big "
            "map: the start area is lit in yellow and every other start area of this monster has a pin; click a pin "
            "or an area to start there. The area outlines come from the game's own map pictures.")
        )),
        ("Size % and Size like", _(H.tip("Size")) + _("\n\n") + _(H.SIZE_TIP)),
        ("Strength like, Health, Attack, Toughness", (
            _("'Strength like' sets Health, Attack and Toughness (and the hidden stamina and size spread) to the typical "
            "values of the game's own quests of that hub and star rank.\n\n"
            "Health: ") + _(H.TEXT["Nando_hp"]) + _("\nAttack: ") + _(H.TEXT["Nando_at"]) + _("\nToughness: ") + _(H.TEXT["Nando_etc"])
            + _("\n\nThe line under each slider gives the real multiplier and the rank it matches. Above the hardest row "
            "that any game quest uses, the label is Nightmare: harder than anything in the game.")
        )),
        ("Count", _(H.tip("Num")) + _(" (Shown only when the quest has a single large monster, or in developer mode.)")),
        ("How the monsters arrive", _(H.ARRIVAL_TIP) + _("\n\n") + _(H.ARRIVAL_NOTE)),
        ("Small monsters", (
            _(H.SPAWN_TIP) + _("\n\nAdd a species, Change..., Remove: edit the list. 'Fill from zone and rank...': ")
            + _(H.SPAWN_FILL_TIP) + _("\n\nStrength of all small monsters: ") + _(H.tip("zako_rows"))
        )),
        ("Developer mode: per-monster details", (
            _("Stamina: ") + _(H.tip("Stamina")) + _("\n\n"
            "Start type: the raw number behind 'Starts in'.\n\n"
            "Size spread: ") + _(H.tip("Sizeparam")) + _("\n\n"
            "Set type: ") + _(H.tip("Settype")) + _("\n\n"
            "Nando2: ") + _(H.tip("Nando2")) + _("\n\n"
            "Main small-monster species: ") + _(H.tip("main_zako1")) + _(" ") + _(H.tip("main_zako2"))
        )),
    ]


def _supply():
    return [
        ("The supply box", _(H.tip("item_set_no")) + _("\n\n'Choose another supply box...' lists the game's boxes; search "
         "for an item to find the boxes that contain it. 'Fill from zone and rank...' picks the box that the game's "
         "quests use on this zone at the chosen rank.")),
        ("Your own box", (
            _("'Make my own box' copies the current box into a box of yours, where you choose every item (up to 40 "
            "different items, 99 of each) and give it a name. A quest does not contain its box, only a number: the "
            "editor uses one of the 10 box numbers that no game quest uses, and writes your items into a supply file "
            "for that number.\n\n"
            "The files must be installed: the 'Install the supply files into Citra' button copies them into Citra's "
            "load/mods folder; on a real 3DS copy output/MH3U_Supply_Mod/romfs into luma/titles/<title id>/romfs (") + TITLES + _("). "
            "Without the files the game opens the box it normally has under that number. Every player of a "
            "multiplayer quest needs the same files.")
        )),
        ("My supply boxes (manager)", (
            _("The 'Supply boxes' button at the top (also 'My supply boxes...' in the Supply Box tab) opens the manager: "
            "rename a box, edit its items, see which quests use it and whether it is installed in Citra, install it, "
            "remove its file from Citra, or delete the box. Deleting a box also removes its file from Citra, after "
            "listing the quests that use it (they will open the game's own box with that number). Boxes are kept "
            "until you delete them; there is room for 10.")
        )),
        ("Developer mode: later deliveries", (
            _("Timed delivery: ") + _(H.tip("supp_set_no")) + _("\n\nHunt delivery, monster: ") + _(H.tip("supp_time_flag"))
            + _("\n\nHunt delivery, how many: ") + _(H.tip("supp_enemy_type")) + _("\n\nVersion 1.1 and older called "
            "these 'Delivery set', 'Time condition', 'Monster condition' and showed a 'Count' that is in fact where "
            "the hunters start (now on the General tab).")
        )),
    ]


def _rewards_text():
    return [
        ("Challenge gear", (
            _(H.GEAR_TIP) + _("\n\nThe Challenge gear tab appears on those quests (in Developer mode on every quest "
            "that carries the gear sets). For each of the 5 sets: the weapon (type, then the weapon), the five armor "
            "pieces, the talisman and its two skills (skill tree and points), the item pouch (24 items) and the ammo "
            "pouch (8 items, for the bowguns). 'Copy the gear of a game quest...' takes the 5 sets and the rank "
            "times of a Challenge quest or Grudge Match. Names are the game's own.")
        )),
        ("Reward tables A and B", _(H.tip("rewards")) + _("\n\nAdd..., Edit..., Remove and ▲ ▼ edit a table (up to 32 lines). "
         "The total chance of a table is shown under it.")),
        ("Fill from the quest's monsters and rank", (
            _("Builds table A from the game's own quests: the materials of each large monster of the quest, then the "
            "other items the game gives at that rank and zone (armor spheres, charms, ores, bones, bugs...). Each item "
            "belongs to the few monsters whose quests give it, so shared materials go to the right monsters. The dialog "
            "says what it is based on. Everything stays editable.")
        )),
        ("Text tab", (
            _("The game stores every text in English, French, German, Italian and Spanish; the console language decides "
            "which one you see. Quest name, Objective text, Sub-objective, Failure conditions, Client and Description "
            "are edited per language; 'Copy this language to the 4 others' fills the other languages with the current "
            "one.")
        )),
    ]


def _values():
    return [
        ("Rank labels of the Health / Attack / Toughness rows", H.tier_table()),
        ("Health multipliers by star rank", H.table("hp")),
        ("Attack multipliers by star rank", H.table("atk")),
        ("Damage taken by star rank", H.table("dmg")),
        ("Where these numbers come from", (
            _("They are medians measured on the game's own quests (365 quests of the base game plus the event and "
            "challenge quests). Health, Attack and Toughness are rows (0-127) of the game's 128-row difficulty table, "
            "not percentages: the editor shows the multiplier of the row and the rank it matches. A table with the "
            "typical fee, reward and HR points of each hub and star rank is at the bottom of this page in the editor.")
        )),
    ]


def _files():
    return [
        ("What the editor changes", (
            _("1. Your save's quest files: quest1, quest2, quest3 (event quests) and quest4 (challenge quests), in\n")
            + f"   {CITRA_USER}\\{SAVE_DIR}\n" +
            _("   (the exact folder is found automatically). This is the only game data written by an ordinary save.\n"
            "2. Optional mods, written in the editor's own output folder and copied into Citra on request:\n"
            "   output/MH3U_Supply_Mod/romfs (your own supply boxes) and output/MH3U_Quest_Mod/romfs (edited base-game "
            "quests), installed into <Citra>/load/mods/<title id>/romfs, title id ") + TITLES + _(".\n"
            "   The Monster pack (ROM hack, only if you build and install it) goes into <Citra>/load/mods/<title id>/: "
            "romfs/arc/enemy (47 monster files), exefs/code.ips and mhqe_monster_pack.json.\n"
            "3. Files next to the program: settings.json, custom_supply.json, backups/, library/, error_log.txt (only "
            "if something went wrong).")
        )),
        ("What to back up yourself", (
            _("Before the first save, copy your save's extra data folder (the 'user' folder above holding quest1-quest4) "
            "and, if you use mods, the folder <Citra>/load/mods/<title id>. On a real 3DS, back up the save with "
            "Checkpoint or JKSM. The editor makes its own backups too, but a copy you made yourself is the one that "
            "cannot be touched by a bug.")
        )),
        ("The editor's backups", (
            _("Every save first makes a full backup of quest1..quest4 (backups/full/) and keeps a separate copy of every "
            "quest it replaces, edits or clears (backups/quests/), so a single quest can be put back in its slot. "
            "backups/original/ keeps the very first version of each file and is never deleted. Restoring a backup backs "
            "up the current files first. Everything is listed in In-game quests > Backups.\n\n"
            "Old backups are cleaned up automatically to save space: by default the 20 most recent full backups and "
            "the 5 most recent copies of each quest are kept (Settings > Backups). Never deleted, whatever the "
            "settings: backups/original/, the very first full backup and the first copy of every quest (marked with "
            "a lock). The cleanup only ever deletes inside backups/full and backups/quests.")
        )),
        ("Good habits", (
            _("Close Citra before saving. Test on Citra before a real 3DS. Keep one slot per experiment. Share quests as "
            ".mh3uq files from the library rather than the raw save files.")
        )),
    ]


def _pack():
    return [
        ("What it does", (
            _("The game keeps, inside its program (code.bin), a table of the maps where each large monster may start a "
            "quest. A monster put on another map is silently skipped. Each monster's own file also holds its spawn "
            "areas, routes between areas and special moves for each map it knows. The Monster pack gives every large "
            "monster the maps it is missing: for each new map it borrows the start positions and map data of a "
            "'donor' monster that lives there (same kind of habitat and size where possible), and adds them to the "
            "monster's tables. For each new map it also picks, among the game's own start lists for that map, the one "
            "offering the most start areas the monster can use. The result: 497 new monster/map combinations: every "
            "one of 47 large monsters can start on all 14 maps.\n\n"
            "The siege maps follow the game's own example: on the Underwater Ruin a monster gets only a start point "
            "in area 3, exactly like Abyssal Lagiacrus in the game (which has no other data for that map); on the "
            "Great Desert it gets Jhen Mohran's data; on the Tainted Sea Dire Miralis'.")
        )),
        ("What it changes (ROM hack)", (
            _("It is a mod, built on your PC from your own extracted game: 47 files romfs/arc/enemy/emNNN.arc, a 7 KB "
            "patch exefs/code.ips (only new start lists and the extended size table, written in unused space of the "
            "program and over the old lists it replaces, one pointer per monster and one for the size table) and "
            "mhqe_monster_pack.json. Your ROM and your save are not modified; removing the mod (button "
            "'Remove from Citra') brings the game back exactly. It can not be combined with another code.ips/code.bin "
            "mod.")
        )),
        ("Great Desert: the Dragonship", (
            _("Every Great Desert quest of the game is a Dragonship fight against a Jhen Mohran, and all of them are "
            "set up the same way: objective A 'Slay or repel' the Jhen Mohran, objective B the Dragonship's integrity "
            "(1000, or 1300 against Hallowed Jhen Mohran), the 'Single objective' pattern and a Dragonship flag in the "
            "category. A quest without the integrity starts with a Dragonship at 0: it is destroyed and the quest "
            "fails at once. The General tab's 'Set up the Dragonship fight' button (also offered when you choose the "
            "Great Desert map) writes all of this, and the game's failure text in the five languages.")
        )),
        ("Great Desert: area 2", (
            _("In the Jhen Mohran fight the sand ship moves from area 1 to area 2, so a monster that starts in area 1 "
            "is left behind. Jhen Mohran's own start list has only area 1, but its spawn data (which the pack lends "
            "to the other monsters) has both areas. The pack therefore gives the other monsters a start list of "
            "their own on the Great Desert: start 0 = area 1, start 1 = area 2 (choose it in the card's 'Starts in' "
            "list or on the map). Untested in the game.")
        )),
        ("Big sizes", (
            _("A quest stores a monster's size in one byte, so 255 % is the most it can hold. The game then adds a value "
            "taken from a 'size spread' table (chosen by the quest), with no upper limit. The pack moves that table "
            "and adds 19 exact sizes, +100 % to +1900 %, so a quest can make a monster up to 2000 % ('Size %' in "
            "Developer mode). Such a quest needs the pack installed: without it the game reads past its own table. "
            "The table lookup was checked against the game's code, but giant monsters were not tried in the game: "
            "they may clip through walls, get stuck in area exits or be hard to reach.")
        )),
        ("Left out", (
            _("Ceadeus, Goldbeard Ceadeus, Jhen Mohran and Hallowed Jhen Mohran stay on their own maps (they still lend "
            "their map data to the others). Small monsters are not concerned.")
        )),
        ("How to use it", (
            _("1. Settings: set your game version and choose the extracted romfs folder (exefs/code.bin must be next to "
            "it).\n"
            "2. Monster pack page: 'Build the pack from my game' (a few seconds), then 'Install in Citra' (close Citra "
            "first). On a real 3DS, copy the content of the pack folder into luma/titles/<title id>/ and enable game "
            "patching in Luma.\n"
            "3. Make your quest as usual: the monster card says 'thanks to the Monster pack'. Choose where it starts in "
            "the card's 'Starts in' list (the checks say when a number does not exist for its start list).\n"
            "4. Restart the game and test the quest.")
        )),
        ("Risks", (
            _("Only Zinogre on Sandy Plains was tested in the game. Every other combination follows the same rules but is "
            "untested: the monster may get stuck, move oddly, or the game may crash when the quest loads. Riskier: the "
            "water arenas (a monster that can not swim), Sacred Land and Tower, the siege maps (their scripts are made "
            "for Jhen Mohran, Ceadeus or Dire Miralis), and Alatreon or Dire Miralis away from their own maps; the table "
            "marks them '+!'. Back up your save first.")
        )),
        ("Multiplayer", (
            _("Every player in a local game must have the same pack installed, or the others do not see the monster (or "
            "worse). Built from the same game version the pack is identical for everybody: compare the fingerprint shown on the Monster pack page.")
        )),
    ]


def _limits():
    return [
        ("Confirmed in the game", (
            _("Arrival patterns: 'one after another', 'the first, then the other two together' and 'the first two "
            "together, then the last' work as described; with 'all at the start' every monster is in the zone from the "
            "beginning and the quest ends when the target monsters are slain.\n"
            "Monster placement: a monster the game does not allow on a map is skipped (Zinogre on Sandy Plains never "
            "appeared); with the Monster pack it appears (Zinogre on Sandy Plains, Citra). The opposite case, a monster "
            "allowed on a map without its spawn data, crashes the game when the quest loads.\n"
            "Time limit: up to 98 minutes the clock counts down; from 99 minutes it is frozen.\n"
            "Environment: Unstable is shown on the quest board when the chance of roaming monsters is above 0.")
        )),
        ("Read from the game's files, not seen in play", (
            _("The meaning of most quest fields comes from comparing the game's own quests (the (i) texts say 'not "
            "confirmed' where that is all there is). Not every pattern that the editor allows appears in the game: "
            "the three-monsters-at-once pattern and the five-monster 'one after the other' follow the same rule but "
            "never appear in a game quest, so test them.")
        )),
        ("Known limits", (
            _("The monsters that roam an Unstable zone cannot be chosen: their list is stored in the game, not in the "
            "quest. There is no 'enraged' or 'charged' setting in the quest file: the game's 'Clashing Fists!' and "
            "'Descent into Hades' use King Size monsters. The block at the end of an event quest that is not understood "
            "is kept unchanged.\n"
            "Versions: the European version was studied and tested. The North American version was compared file by "
            "file with it: same quest format and base quests, same monster files, only the program id, the save "
            "folder (00000AE4) and the 'us' folder of the base quests differ. Its event quest files could not be "
            "checked on a real US save yet.")
        )),
        ("Not tested yet", (
            _("The editor was tested on Windows with Citra only, with the European version. A real 3DS (the files are "
            "the same, but nobody has tried on hardware yet), the North American version in play, Linux and macOS are "
            "untested (start the editor with 'Launch Quest Editor.command' on macOS or launch_quest_editor.sh on Linux; "
            "Python 3.10 or newer with Tk is needed). In the Monster pack, only Zinogre on Sandy Plains was tried in the game. Please report what you "
            "find.")
        )),
    ]
