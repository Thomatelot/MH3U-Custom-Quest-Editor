# Changelog

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
