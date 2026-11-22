# Changelog

## 1.8.1

Testers' reports. Checked by the tests and the scripted run of the window; **untested in the game**
unless said otherwise.

* **Fix: starts of your own broke the Monster pack** (a tester's *HYPER PECO*: after building the pack
  with a Qurupeco start of his own, no Qurupeco appeared anywhere, nor his Alatreon in the Great Desert;
  removing the starts and building again fixed it). The cause, found in the game's code: the start
  positions are not in code.bin's start lists but written into them when the game starts (by one of its
  static initialisers, the same address in the European and North American versions). To make room,
  1.8.0 shared the game's "duplicate" start lists and wrote its own lists over the freed ones; at boot
  the game wrote its positions over them again. Now:
  * nothing is written over the game's start lists any more (the pack checks it; a test runs the game's
    initialisers in an emulator and finds none of the pack's bytes rewritten);
  * the room comes from the placement lists instead: the game takes the first entry of a map in a
    monster's list, so a list can be "what differs, then another monster's list". About 4 KB are free
    once every monster has every map: about fifteen monster/map pairs with starts of your own;
  * a start of your own now has a real start point: the monster's own start in that area, else the start
    point of a monster the game starts there (shown in *My monster starts*; until now its position was
    0, 0, 0). Areas where the game starts no monster are refused (the base camp of most maps);
  * a pack built by 1.8.0 with starts of your own or roaming lists 214-255 is flagged on the Monster pack
    page and in the quest checks: **build the pack again and install it.**
* **Reward tables A and B** (found by a tester): the 64 reward slots of a quest hold two tables that
  alternate line by line, A on the even slots and B on the odd ones; each table ends at its first empty
  line and the other goes on (checked on the game's 403 quests: every table adds up to 100 %). Until now
  the editor showed one list and stopped at the first gap, so the last lines of some game quests were
  missing ("Forecast: Lagombi", a tester's Gobul quest) and an older quest may now show some items in
  table B: check the totals. The Rewards tab shows tables A and B (32 lines each), the total in orange when
  it is not 100 %, and *To 100 %* to fix it.
* **Filling the rewards from the monsters:** table A gets the monsters' materials, table B the other items
  of that rank and zone, each table at 100 % (until now everything went to one list at 200 %). Monsters
  with few game quests get all their materials: Ceadeus now gets Ceadeus Hide, Ceadeus Scale, Luminous
  Organ, Ceadeus Fur and Deep Dragongem instead of the hide alone (an item that one game quest gives now
  belongs to that quest's monster; one that two or three quests give can belong to each of their monsters).
* **Go back, clean up Citra** (Settings): go back to the version of the editor you had before the last
  update (also in Settings > Updates); remove the editor's files from Citra's mods folder (base-game
  quests, supply boxes, Monster pack; other mods are left alone); or go back to the game as it was before
  the editor (the same, plus the event quest files put back as they were before your first change). Every
  file removed or replaced is copied first to `backups/cleanup` in the editor's folder, and *Put back the
  last clean-up* undoes it.
* **Moga Village and Port Tanzia (map 9):** a tester saw no Barroth appear in Port Tanzia, after
  Lagiacrus. Lagiacrus' start point is inside the Port's walls, so the hubs simply do not take large
  monsters: the checks now say so (use map 9 for gathering or small monsters).

## 1.8.0

Reports from the testers. Checked by the tests and the scripted run of the window; **untested in the
game** unless said otherwise.

* **Fix: removing a small-monster species gave an "Unexpected error"** (`'<' not supported between
  instances of 'tuple' and 'int'`). 1.7.0 put the boulders in the "Other" group of the species list, next
  to "(none)", and sorting that group failed.
* **Star rank 0 to 9:** the game's quests never go above 9 (Village 1-9, Port and event quests 1-8), and
  the editor warned about 10 while offering it. A quest that already has 10 keeps it (shown "not used by
  the game"). The phone notebook offers Village 1-9 and Port 1-8.
* **Save button on the quest lists** (In-game quests, Library, Base game; next to the number of quests):
  writes every quest marked * (the same as Ctrl+S). The save's quest files hold several quests each, so it saves every change, not
  only the selected quest.
* **Portable Citra:** the editor now finds Citra's `load` folder in the Citra that holds the chosen save
  folder (a portable Citra keeps everything in a `user` folder next to the program), and a new *Choose
  Citra's folder...* button (Settings, My supply boxes, and offered when installing) points it at any
  Citra. Used for the supply files of your own boxes, the base-game mod and the Monster pack. The `load`
  folder is made if needed.
* **Monster data:** the Monsters tab shows how much monster data the quest makes the game load (large,
  small and roaming monsters), and the checks warn above what any quest of the game loads on a map of the
  same kind. A tester's quest that stayed on *Now Loading* for ever had 4 large monsters, 8 small species
  and a roaming monster on the Flooded Forest: 18.7 MB, where the game's quests load 14.5 MB at most on maps
  of several areas. The real limit is not known; the editor only compares with the game's quests.
* **Underwater Ruin:** a note when a quest has no Ceadeus and the hunters start at the camp (area 1 is
  closed by rocks only Ceadeus breaks, the way from the camp leads to the end of area 2, as a tester saw
  in the game; the game's quests without Ceadeus start the hunters in area 3).
* **Night on the maps the game only uses by day:** the Underwater Ruin, the Arena and the Water Arena have
  a night version that the game never uses (read in the game's quest map -> stage table and files). A
  tester played the Underwater Ruin's: everything works, only the light and shading differ. The checks
  now say this as a note instead of a warning; the Sacred Land, the Tainted Sea and the arena variants
  have no night version (the same map is loaded).
* **Roaming monsters, read in the game's code:**
  * the five settings are now named by what the game does with them: *Chance at the start of the hunt*
    (rolled once), *Chance each time one may come* (the "second %": the chance at each try, 20 less after
    each one that came; a tester read it as minutes), *How many can come* (until now "at most at the same
    time"; the game stops at 3) and *Only when called (Qurupeco)* (until now "always comes": with it no
    roaming monster comes on its own, only when called; set in the game's 11 Qurupeco quests). All four
    are now in the standard mode;
  * **your own lists: Health, Attack, Toughness and Size of each monster** can be changed (with the
    multipliers), plus size spread, stamina, start, level, zenny and HR points in Developer mode. When a
    roaming monster comes, the game builds it from these fields exactly like a quest's monster;
  * **a list holds 3 monsters at most:** the game only draws among the first 3 (its own lists have 1 to 3),
    so the 4th to 8th monster that the editor allowed were never used;
  * **42 more list numbers (214 to 255):** the list number of a quest is one byte and the game does not
    check it, so the Monster pack can move the game's table of lists to a bigger copy (two words of the
    program point to it). Used only when you make such a list; the pack then also shares the game's
    duplicate start lists for room, as for starts of your own. Untested in the game;
  * *Unstable* no longer copies the settings of a Qurupeco quest into a quest without a Qurupeco (its
    roaming monster only comes when called, so none would ever come), and the checks report it.
* **Great Desert without a Jhen Mohran:** a warning when the quest has no Dragonship integrity (objective
  B): the ship can then be destroyed as soon as the quest starts.
* **Quests from the phone:**
  * maps whose game quests are all siege fights (the Great Desert) now use one of them, set up as a
    Dragonship fight with a Jhen Mohran, or with the Dragonship integrity kept as objective B without one;
  * the arena variants (no game quest uses them) use a quest of the same arena (Arena, Water Arena);
  * a quest made from a game quest now gets the small monsters of that quest (before, the copy had no
    room for them and the quest came without any). The same for *New quest* in the library.
* **Starts of your own (Developer mode), testers' request:**
  * *Add a new start...* at the end of a monster card's *Starts in* list opens *My monster starts* with
    a new start for that monster and map;
  * the kind of start is chosen by the testers' names, bytes 11 and 12 of the start record: Normal
    (00 00), Normal+ (00 01), Super 1 (01 00, Brachydios' charged start), Super 1+ (01 01), Super 2 and
    Super 3 (02 01, 03 01, the charged Zinogres), for every monster (unknown effect outside the
    monsters the game gives them to);
  * any area where some large monster has positions: where this monster has none, the Monster pack
    copies the positions of another monster there (shown in the list). The base camp of most maps has
    none, so it stays out. Untested in the game.
* **Phone notebook 1.1** (new APK, same signature: install it over the old one). New options, as in the
  editor's standard mode: where the hunters start, Stable / Unstable (roaming monsters), the supply box (a
  game box, with its items), where each large monster starts, custom Health / Attack / Toughness rows
  (with the multipliers), small monsters (as the game's quests, or none) and their strength. Older drafts
  keep their meaning.

## 1.7.0

Ideas from the testers. Everything below is checked against the game's files and by the tests, but
**untested in the game**: please report what you see.

* **Any small monster on any map**, boulders included. The game keeps no list of maps for small
  monsters (they are not in the placement table of the large ones) and already shows some of them on
  maps where they have no data of their own (Bullfango has none at all). The species the game never puts
  on a map are listed last in *Add a species* and marked * in the list; they borrow the places of the
  map's own small monsters.
* **Every small-monster place is editable**: *Edit places...* (Small monsters) lists each place by area:
  species, area, how many at once, how many times they come back once slain (1 to 8, or again and again),
  variant (with how often the game uses it) and position, picked among the game's own positions in that
  area (raw coordinates in Developer mode). The 45-byte record was read on the game's 11,383 places.
* **Roaming monsters on one-area maps** (Arena, Water Arena...): *Unstable* now works on every map. When no
  game quest of the map has roaming monsters, the settings of a quest of another map are used, with a note.
* **Monster categories as in the game:** Volvidon is a Fanged Beast (it was among the Leviathans), and
  Royal Ludroth, Purple Ludroth, Gobul, Agnaktor and Glacial Agnaktor are Leviathans (they were among the
  Piscine Wyverns), in the editor and in the phone notebook (new APK).
* **Monster starts of your own** (Monster pack, Developer mode): *My monster starts...* (Monster pack
  page, or a monster card's details) adds start records: another area of a map, or one of the game's
  special forms (Brachydios' 1, the charged Zinogre's 2 and 3). They are added after the game's starts,
  so the game's quests do not change; the *Starts in* list shows them as "your start". To make room the
  pack points the game's start lists that are identical but for the monster number to one copy.
* **Experiment: Moga Village or Port Tanzia as a quest map** (Monster pack, Developer mode). Quest map 9 is
  never used by the game's quests (it loads the Arena); the pack can make it load the Village or the Port
  through the game's quest map -> stage table (3 bytes). Nobody knows yet whether the game accepts it.
  Large monsters there use their Arena positions; small monsters get one place in the middle of each
  area, to move by hand (the box of each area is shown).
* The Monster pack is now built in a separate folder first: if building fails, the pack built before is
  kept.
* Text fixes: the Environment help (roaming monsters can be chosen since 1.5), the guide's limits and the
  Monster pack's numbers (51 monsters, 549 combinations since 1.5).

## 1.6.2

* **Choosing the extracted game is easier (bug reported by a US player).** *Choose the romfs folder* only
  accepted the `romfs` folder itself; picking the folder of a dump (Citra or Azahar's `dump`, the
  extraction's main folder, `ExtractedRomFS`...) gave "This does not look like the game's romfs folder"
  and, misleadingly, spoke of `romfs/quest/eu` to US players. The editor now finds the game's files in the
  folder picked, in its subfolders or just above it, for both versions (with both inside, the version the
  editor is set to), and otherwise says what to choose.

## 1.6.1

* **New base-game quests now appear in the game.** The game only loads the quests named in its
  `quest.list` (loose in `romfs/quest/<eu|us>/` and inside `quest00.arc`), and the editor did not add the
  new ones there. Found by a tester who added quest 1120 by hand; the editor now writes the same bytes, in
  both places. A mod saved with an older version is written again when the editor starts: install it again.
* **Update from the editor.** *Settings > Check for updates...*: shows what changed on GitHub and updates
  in one click, replacing only the program files. Your library, boxes, roaming lists, base-game edits,
  settings, backups and mods are kept, and a copy of them and of the old version is saved first in
  `update_backups/` (*Go back to version ...* undoes the update). The editor only goes online from that
  window.

## 1.6.0

* **Phone notebook (Android app).** `android/MH3U-Quest-Notebook.apk`: write quests on the phone (texts,
  stars, map, monsters with size and strength, objective, money, who can join, day or night, rewards),
  offline, in English or French, then save them as `.mh3ud` files to Google Drive or Downloads, or share
  them. Library page, **From phone...**: each draft becomes a library quest, made from the game quest of
  the same map that fits best, with the supply box (and automatic rewards) from the game's quests and a
  report of what was filled in. Not yet tried on a real phone.

## 1.5.0

Ideas and research from testers, checked against the game's code (EU and US).

* **Roaming monsters you can see and choose.** The Environment section shows which monsters roam and their
  chance. "Choose the roaming monsters..." lists the 188 lists of the game, for any map. "My roaming
  lists..." makes lists of your own in the numbers the game leaves empty; the Monster pack writes them
  into the game.
* **New Village and Port quests that count.** Base game page, "New quest...": the quest is added to
  quest00.arc. The Monster pack registers its number in the game's quest list, so the game records it as
  cleared. "Key quest of" (General tab, Progress) makes a quest a key quest of an urgent quest; the urgent
  quest then waits for it too. The tab says what opens each quest and which urgent quest it counts for.
* **Special forms** (Starts in list): the starts that give Brachydios, Zinogre and Stygian Zinogre their
  special form (as in "Clashing Fists!" and "Descent into Hades") are marked.
* **Arena carves** box (General tab): items instead of monster materials, as in the arena quests, or the
  other way round.
* **Monster rank** (General tab): low, high or G rank, Village or Port (the game's EnemyLv).
* **Arena quests for 4**: with 4 players and an HR rule, the board line is the arena's "Max
  participants: 4" line.
* **Monster pack: Ceadeus and Jhen Mohran everywhere** (and their variants). The riskiest combinations:
  untested. The pack frees the game's old size table, so big sizes still fit.
* docs/RESEARCH.md: what was found in the game's code, and what a monster is made of (model,
  animations, behaviour) for a later comparison with MHP3rd.

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
