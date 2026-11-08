# Changelog

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
