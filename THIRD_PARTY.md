# Third-party material and data sources

## What this repository contains

* **Code** (`mhqe/`, `tools/`, `tests/`, launchers): written for this project, MIT (see `LICENSE`).
  The quest record layout (field names and offsets), the monster / item / difficulty /
  category-flag / supply tables in `data/` and the monster-to-map spawn rules were first taken
  from **mh3u-quest-studio** by Matt Wood (https://github.com/Matt-Wood-23/mh3u-quest-studio),
  used under the MIT licence reproduced below. The code in `mhqe/` is an independent
  re-implementation that was re-verified against Monster Hunter 3 Ultimate (3DS, EU and US) files: the
  128-row difficulty table was compared with the game's `code.bin` (identical), and all quest
  records round-trip byte for byte.
* **`data/`**: tables of facts about the game that the editor needs to run: names of monsters,
  items, maps; difficulty and category tables; supply box templates; statistics (medians) of the game's
  own quests (`benchmarks.json`); small-monster places and roaming-monster settings per map
  (`spawn_lists.json`, `stray_sets.json`); reward and supply patterns (`autofill.json`,
  `supp_sets.json`); the position of each icon in the game's picture archives (`icons.json`); and
  the start area of each start position, per monster and map (`start_areas.json`, read from the
  placement table of the game's `code.bin`, identical in the EU and US versions); where the hunters
  start (`hunter_starts.json`, read from the 3DS `code.bin`); and the number painted on the in-game
  map for each area (`area_labels.json`), collected in the game by mh3u-quest-studio (MIT, below);
  the centre of each area on the map pictures (`map_zones.json`, mh3u-quest-studio's Wii U area
  markers scaled to the 3DS pictures by `tools/build_map_zones.py`); and the game's own French names
  of items, monsters and maps (`lang/names_fr.json`, read from the game's French text by
  `tools/build_fr_names.py`, like the English names). `lang/fr.json` holds the French translation of
  the editor's own texts, written for this project (MIT).
  They were computed from the author's own copy of the game with the scripts in `tools/`
  (`build_benchmarks.py`, `build_spawns.py`, `build_start_usage.py`). They contain numbers and names,
  not pictures, text blocks, maps, sounds or program code of the game.
* **`data/supp_template.bin`**: a 472-byte skeleton of a supply-box file (the game's serialized
  structure: headers and 40 item slots) that the editor fills with your items to write a new
  supply file. It is the only binary file taken from the game; it holds no program code, text or art.
* **`assets/app_icon*`**: the application icon (a scroll with a wax seal) was drawn for this project
  by `tools/make_icon.py`. It is original and covered by the MIT licence.

## Capcom's pictures (not under the MIT licence)

The monster icons, item icons and map pictures in `assets/` (`monsters_27.png`, `monsters_54.png`,
`items.png`, `maps/`) are **Capcom's artwork**, taken from the game's own files
(`romfs/arc/ID/ID_com_eng.arc`, `romfs/arc/ID/map/*.arc`, and item colours from `exefs/code.bin`) with
`tools/build_assets.py` (`mhqe/artbuild.py`) and reduced to small icons. They are included only so that
the editor can show the monsters, items and maps it edits, as many fan tools do. They remain Capcom's
property and are **not** covered by this project's licence. The same builder is in the editor
(Settings > *Rebuild the pictures from my game...*) so the pictures can be regenerated from your own
copy of the game. If you are a rights holder and want them removed, open an Issue and they will be.

The MH3U wiki pages saved by the author were only used while developing, to identify and double-check
monster icons and to cross-check the *Environment* and roaming-monster names of quests. No wiki text
or image is included.

Monster Hunter is a trademark of Capcom. This project is not affiliated with Capcom or Nintendo.

---

## mh3u-quest-studio licence (MIT)

Copyright (c) 2026 Matt Wood

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
