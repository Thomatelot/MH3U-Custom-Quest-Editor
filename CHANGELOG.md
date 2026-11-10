# Changelog

## 1.4.1

* **Great Desert: the Dragonship fight.** Every Great Desert quest of the game is set up the same
  way: objective A "Slay or repel" the Jhen Mohran, objective B the Dragonship's integrity (1000, or
  1300 against Hallowed Jhen Mohran), the "Single objective" pattern and a Dragonship flag in the
  category. A quest made from another template (a Ceadeus quest, for example) has no integrity, so
  the Dragonship is destroyed and the quest fails as soon as it starts. New "Set up the Dragonship
  fight" button on the General tab (also offered when the Great Desert map is chosen); it also
  writes the game's failure text in the five languages. The checks now report this, and a Ceadeus
  objective outside the Underwater Ruin. Objective type 0x2000 is now named "Dragonship integrity".
* Fixes: the night warning no longer says the Great Desert has no night quest (Festival on the Sea of
  Sand is one); the quest board line now says where it shows in the game (the quest's details on
  the quest board).

## 1.4.0

* **Who can join** (General tab): minimum Hunter Rank (HR 2 to 9), maximum number of players (1 to 3)
  and "no armor or talismans", the two rules the game enforces when a hunter starts or joins the
  quest. The editor sets the matching line of the quest board (the game's own texts, in English or
  French) and the checks warn when the board line and the rules disagree. Meaning from
  mh3u-quest-studio (Wii U, confirmed in the game), checked against every 3DS quest.
* **Day or night** (General tab): every quest of the game is one or the other (category bits
  0x10000 / 0x20000); the checks warn about night on maps the game only uses by day.
* **Challenge gear** (new tab on Challenge quests 61000-61009 and Grudge Matches 60000-60011): the
  5 gear sets the hunters choose from (weapon, armor, talisman and skills, item and ammo pouches)
  and the S / A rank times, with the game's own equipment names; copy the gear of another
  Challenge quest. This is the only "weapon rule" MH3U has: elsewhere hunters keep their own gear.
* **Monster pack: Great Desert area 2.** On the Great Desert the other monsters get their own start
  list: start 0 = area 1, start 1 = area 2, so a monster can wait in area 2 where the sand ship
  arrives instead of being left behind in area 1. Rebuild and reinstall the pack (the page says
  when the built pack is from an older version). Untested in the game.
* Fixes: the French interface's header no longer cuts the last buttons; "In the game" and the
  monster pack status lines are translated; talisman skill points are read as the game stores them
  (a signed byte); hunters-start list translated; smaller header buttons so everything fits at
  1280 pixels.

## 1.3.0

* **Start areas on the map.** Each monster card shows the area map with the monster's start area lit
  in yellow; clicking it (or *Map...*) opens the big map, where every start area of that monster has a
  pin and a click on a pin or an area chooses it. The General tab shows where the hunters start on the
  map. The area outlines are taken from the game's own map pictures and placed with mh3u-quest-studio's
  area markers (at exactly one third of the Wii U coordinates on every map).
* **Monster and item browsers.** Monsters are grouped by type (Bird, Flying, Piscine and Brute Wyverns,
  Leviathans, Fanged Beasts and Wyverns, Elder Dragons, small monsters) with the easiest first and
  difficulty stars (an editorial 1-10 ranking shown as 1-5 stars), or listed from Beginner to Hardest.
  Items are grouped in 15 families following the game's icon shapes. A side list filters by group;
  moving the selection no longer redraws the grid.
* **English / French.** *Settings > Language / Langue* (French by default on a French computer). The
  interface, the checks and the built-in guide are translated; item, monster and map names come from
  the game's own French text (tools/build_fr_names.py). Search also accepts the English names.
* **Monster sizes up to 2000 % (Monster pack, Developer mode).** The quest keeps the size in one byte
  (255 % at most); the game adds a value from a size table chosen by Sizeparam, without an upper limit
  (EU code at 0x5C0754). The pack moves that table and adds exact sizes +100 % to +1900 % (Sizeparam
  64 to 82); the editor sets Size and Sizeparam for you. Checks: such a quest needs the pack installed.
  Not tried in the game.
* **Backups clean themselves up.** By default the 20 most recent full backups and the 5 most recent
  copies of each quest are kept (Settings > Backups). Never deleted: the original files, the very first
  full backup and the first copy of each quest (shown with a lock); the cleanup can only delete inside
  backups/full and backups/quests.
* **Copy to my library**: the separate, editable copy of a quest can be opened right away; the original
  is never changed.
* **macOS and Linux:** `Launch Quest Editor.command` and `launch_quest_editor.sh`; more emulator
  folders are found (XDG data folder, Flatpak builds of Citra, Azahar and Lime3DS, macOS Application
  Support); fonts fall back to each system's own. Untested on those systems.
* A thin ornamental band under the header, in the spirit of MH3U's menus.

## 1.2.0

* **Monster pack: every map.** The siege maps (Great Desert, Underwater Ruin, Tainted Sea) are open
  to every large monster too; only Ceadeus, Jhen Mohran and their variants stay on their own maps
  (they still lend their data). 497 combinations, all 14 maps for 47 monsters. On the Underwater
  Ruin a monster gets only a start point in area 3, as Abyssal Lagiacrus has in the game. The pack
  reuses the space of the old start lists, and for each new map picks the game's start list with
  the most start areas the monster can use.
* **Starts in** (monster card, no longer developer-only): the start points the game has for that
  monster on that map, shown with the numbers painted on the in-game map (the game's own area
  numbers differ; version 1.1 showed those). Copies of one species are spread over start points
  that exist.
* **Hunters start** (General tab): base camp, random area (with the game's odds for the map) or
  fixed area, read from the 3DS code (table identical to the Wii U one). The checks say when the
  value does nothing on the map.
* **Field labels corrected:** following mh3u-quest-studio's latest work (the game's own field
  names), checked against all 3DS quests: "Progress level" is the monster rank, "Monster level" is
  the intro cutscene, "Gathering table" is the supply rank plus story step, and the supply
  delivery fields were one field off; the old delivery "Count" was where the hunters start (now on
  the General tab). Quest files are unchanged: only labels and explanations changed.
* Supply auto-fill no longer changes where the hunters start.

## 1.1.0

* **North American version** (title id `00040000000AE400`, save folder `00000AE4`): choose the
  version in *Settings > Game version* (also asked on the first start, and offered when you choose an
  extracted game of the other version). Paths, backups (`backups\us\`) and the base-game mod
  (`quest\us`) follow the version. The US files were compared with the EU ones: same quest format,
  same base quests, same monster files; not yet played on a US game.
* **Monster pack (ROM hack, optional)**, new page: builds from your own extracted game a mod
  (`exefs/code.ips` + 47 monster files) that lets 47 large monsters start on every non-siege map
  (358 new combinations), installs/removes it in Citra, shows a fingerprint so that multiplayer
  partners can check they use the same pack, and a table of which monster can start where.
  Only Zinogre on Sandy Plains was tested in the game. Also as `tools/build_monster_pack.py`.
* Placement findings: the game's placement table lives in `code.bin`; a monster on a map it does
  not allow is skipped (no crash, it never appears). Checks, monster cards and the Guide now say so,
  and know the combinations added by an installed pack.
* **Start positions:** the start area of each position number (Starttype) is read from the game's
  own table and shown in the *Start positions* dialog and on the card; the checks flag a position
  that does not exist for the monster on that map.
* Tests for the new features (`tests/test_v11.py`) and the scripted GUI run.

## 1.0.0 - first public release

First release of the MH3U Custom Quest Editor, for Monster Hunter 3 Ultimate (3DS, European
version, title id `00040000000B1D00`), on Citra or a real 3DS.

* Create, edit, duplicate, export and clear quests in the **event quest** slots (packs 1-3) and the
  **challenge quest** pack of your save; **quest library** of `.mh3uq` files on your PC.
* Quest editor with five tabs: **General**, **Monsters**, **Supply Box**, **Rewards**, **Text**
  (5 languages), and an (i) explanation next to every setting.
* Monsters: up to 5 large monsters, *How the monsters arrive* (all at the start, one after another,
  groups), size presets, *Strength like* rank presets (health / attack / toughness), small-monster
  list per map, unstable environment.
* Supply boxes: the game's boxes, plus your own named boxes (up to 10) with a manager.
* Rewards: auto-fill from the game's own quests, by monster and rank.
* **Base game** page: edit the game's own Village and Port quests as a Citra mod (the ROM is not changed).
* Automatic backups before every save, per-quest backups, and a never-deleted copy of the original files.
* Built-in tabbed **Guide**; two themes (Moga Parchment, Tanzia Night); *Developer mode* for raw fields.
* Pictures of monsters, items and maps are included in `assets/`; they can be rebuilt from your own
  game (Settings > *Rebuild the pictures from my game...*, needs Pillow).
* Tested on Windows with Citra and the European version; see the README for what was and was not tested.
