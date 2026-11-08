# Security and legal

## Reporting a problem

* **A bug, a crash, a quest that does not load:** open an Issue (see *Reporting* in the README).
  Say what you did, the editor's `error_log.txt` if there is one, and whether it was Citra or a real 3DS.
* **A security problem** (for example the editor writing outside the folders it should, or code
  execution from a quest file): please use GitHub's *Report a vulnerability* button on the
  *Security* tab of this repository (private), or open an Issue without technical details and ask
  for a private channel.

**Never attach game files** (ROM, `romfs`, `quest1`..`quest4` from your save, `.supp` files) to an Issue, a Discussion or a pull request. Share a quest as a `.mh3uq` file from the
editor's library instead: it holds one quest record and nothing else (no ROM, no save), and it is
useless without the game. Share quests you made or changed; a quest copied unchanged from the game
is Capcom's data, so do not post those.

## What the editor does and does not do

* It runs **offline**: it never opens a network connection and never sends anything anywhere.
* It only reads and writes in: the folder of your save's quest files (`quest1`..`quest4`) that you
  chose or that was found in Citra's folder; its own folder (`settings.json`, `custom_supply.json`,
  `backups/`, `library/`, `output/`, `error_log.txt`, and `assets/` if you rebuild the pictures); and, only when you press
  the install buttons, the `load/mods/00040000000B1D00/romfs` folder of Citra.
* It never modifies the ROM, the game's `romfs` or `exefs` that you extracted (it only reads them).
* It does not need administrator rights, and it contains no installer or auto-update.
* Quest files (`.mh3uq`) are plain binary data (the same record layout as the game's quest files)
  read by the editor's own parser; nothing in them is executed. Still, only open quests from people
  you trust and keep your backups: a malformed quest can crash the *game*.

## Legal notice

This is an unofficial fan-made tool. It is not affiliated with, endorsed by or supported by Capcom
or Nintendo. *Monster Hunter* is a trademark of Capcom Co., Ltd. All game content belongs to its
owners.

* The repository contains **no game**: no ROM and no extracted game file. You must own a legal copy
  of Monster Hunter 3 Ultimate and dump it yourself. It does include the small monster / item / map
  pictures the editor displays, which are Capcom's artwork (see `THIRD_PARTY.md`).
* Do not share ROMs, extracted game files or your save files.
* The `data/` tables are facts about the game (names, numbers, rules) compiled for this editor; see
  `THIRD_PARTY.md` for where they come from.
* Use at your own risk. Modifying quest files can corrupt a save or make the game crash; the code is
  provided "as is" under the MIT licence (see `LICENSE`), without warranty. **Keep backups.**
* Use it for single-player and with friends who run the same files; do not use modified quests to
  disturb other players online.

If you are a rights holder and think something in this repository should not be here, open an Issue
or contact the author and it will be dealt with promptly.
