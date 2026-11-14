# MH3U Quest Notebook (Android)

A small companion app for the MH3U Custom Quest Editor: write quests on your phone whenever
you have an idea, then send them to the PC, where the editor turns them into real quests.

**Install:** copy `MH3U-Quest-Notebook.apk` to the phone and open it (Android 5.0 or newer).
Android asks once to allow installing apps from the app you opened it with (Files, Drive,
your browser...). The app needs no permission and never goes on the Internet.

## What you can write

- Name, client, description, objective text, sub-objective, failure conditions.
- Village or Port, star rank, monster rank, map, time limit (or a frozen clock), fee, reward,
  HR points (the usual values of the game's quests of that rank are filled in for you).
- Who can join (Hunter Rank, players, no armor), day or night, arena carves.
- Up to five large monsters with their size and strength, and how they arrive.
- The objective: hunt, capture or slay the monsters, deliver an item, or slay small monsters.
- Rewards: automatic (chosen on the PC from the game's quests) or your own list.

Quests are kept on the phone. The **Send** tab checks the quest and saves it as a `.mh3ud` file
(to Google Drive, Downloads...) or shares it (Drive, e-mail, Quick Share...).
The ⋮ menu backs up every quest in one file and imports files.

## On the PC

Library page → **From phone...** → pick one or more `.mh3ud` files. For each quest the editor
copies the game quest of the same map that fits best (the game's files must be set in Settings),
applies everything you wrote, fills in the supply box (and the rewards if they were automatic)
from the game's quests, and adds the result to your library. A report says what was filled in;
open the quest to check it, then send it to the game as usual.

Texts are written in one language and copied into the game's five languages.

## For developers

- `web/`: the app itself (HTML / JavaScript, works in any browser too: open `web/index.html`
  after copying the pictures as `build_apk.sh` does).
  `web/data.js` is built by `tools/build_phone_data.py` from the editor's tables: run it again
  when they change.
- `native/`: the Android part, an apktool project. The native code (`native/smali`) only shows the
  page in a WebView and adds what a page cannot do: Android's back button, the "save to" and "open"
  file pickers, and the share sheet (through a small read-only file provider).
- `build_apk.sh`: builds and signs the APK without the Android SDK (see the comments in it).
- The draft format is read by `mhqe/phone.py` (tests: `tests/test_phone.py`).
