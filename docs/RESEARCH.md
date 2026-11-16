# Research notes (game code and files)

What the editor knows about MH3U beyond the quest files, and how it was found. Addresses are those of
the EU and US 1.0 `exefs/code.bin` (identical at every address below; virtual address = file offset +
0x100000). Nothing here was tested in the game unless it says so.

## Start records and "special forms" (1.5)
Placement table (VA 0xC38348): 86 pointers, one per monster, to lists of (internal stage, pointer to
start records). A start record is 56 bytes: +0 monster, +8 pack id (255, or 16/17/18 for the
Great Jaggi/Baggi/Wroggi packs), +9 start area, **+11 form**, +12 0/1/2 (unknown), +48 0/1.
The quest's Starttype picks a record (function 0x631014). Function 0x5C6DEC copies the record into the
monster's spawn slot (form -> slot+3). The form is 0 everywhere except 13 records: Brachydios Volcano
start 1 = 1 ("Clashing Fists!"), Zinogre and Stygian Zinogre = 2 or 3 on five maps ("Descent into Hades"
= Volcano start 1, form 3). The same byte selects the fish species for em032, so the game passes it to
every monster; what forms 1-3 do for other monsters is unknown (a tester reports a change on Dire
Miralis).

## Roaming-monster lists (1.5)
Pointer table at file 0xB27900 (slot 0 empty); quest field nora_set_table = slot. Lists from 0xB233F8,
30-byte entries (15 u16): species, health, attack, defence, size %, ?, size spread, 0, ?, ?, chance %,
0, zenny, HR points, level; closed by an all-zero entry. 188 lists, 25 empty slots (37-39, 85-100,
204-209). Function 0x62B724 keeps the entries whose level fits the hunters, then draws by chance.
Checked: event quest "An Ominous Cry" uses slot 212 = Savage Deviljho 100 % (as a tester reported).

## Quest list, "cleared" flags, key quests (1.5)
- Master list at file 0xB43370: 504 u16 quest numbers, 0 = unused (82 unused), 0xFFFF end. Index = the
  quest's "cleared" bit in the save (0x9988D0 number -> index, 0x99B62C read, 0x99B73C set). A quest
  missing from the list is never recorded as cleared.
- The counter lists (function 0x623EC8) are NOT a list in the code: every q_*.quest file of quest00.arc
  is loaded and sorted by number (Village 1000-10999, Port 11000-12899) and star rank.
- Each quest's OpenFlag block (after the two Challenge rank times): need u64, give u64, count u8.
  For every cleared quest of the hub, each bit of its "give" adds one to a counter; a quest is listed
  when the counters of its "need" bits add up to "count". Key quests = the quests whose "give" holds
  the bit their urgent quest needs (Port 1 star: 11105 11109 11110 11112 give bit 3, 12201 needs bit 3
  four times). Bit 63 = "previous urgent quest". Some "need" bits (56 for G rank) are given by no
  quest: those quests open another way (Hunter Rank).

## Arena carves and monster rank (1.5)
- Category bits 0x08000000 and 0x20000000 are both set in exactly the 22 Grudge/Challenge quests
  (0x20000000 also in gathering quests). A tester got normal carves back by clearing category bits.
  Which bit alone decides is not established.
- prog_no (the game's EnemyLv) 0-4 = low/high/G rank, Village/Port; G rank monsters use their G rank
  moves. The supply-box code reads the rank from the quest number instead (0xBEAE98 range table:
  1000, 1600, 2000, 2600, 11000, 11300, 11600, 12000, 12300, 12600, 12900, 20100, 20200, 20300...).
  Which of the two decides G rank rewards is not established.

## Small-monster places (1.7)
After the quest's 21-byte small-monster header and a u32 count, each place is a 45-byte record:
+0 species (u32), +4 how many times it comes back once slain (u32: 1-8, 255 = again and again), +14 area,
+15 how many appear at once, +16 variant (a young Aptonoth...), +21 six floats: x, y, z, 0, facing
(0-65535 = one turn), 0. The other bytes are kept as they are. Checked on the 11,383 records of the
game's quests (a tester's notes gave the same reading). Small monsters are not in the placement table
of the large ones, and the game already puts some of them on maps where their em_mappos00 has no data
for that stage (Bullfango has none at all; Uroktor on the Volcano), so any species on any map should
work; untested.

## Your own start records (1.7)
The pack appends records to a monster's start list for a map: a copy of its first record there with
+9 (area), +11 (form) and +12 changed; the record has no position, the game takes it from the
monster's em_mappos00, so the area must be one of those. With the whole pack only a few hundred bytes of
code.bin stay free. 74 of the game's 152 start lists are also pointed to by the game's code (literal
pools, e.g. 0xAA13C0), the other 78 only by the placement lists; among those, the lists identical to
another one but for +0 (monster number) of their records are pointed to their twin (as the pack already
lends start lists, tested with Zinogre on Sandy Plains), which frees 6,160 bytes (EU and US).

## Quest map -> stage (1.7)
- VA 0xBEAEEE (file 0xAEAEEE), 16 x 2 bytes, index = the quest's map: byte 0 is the stage loaded,
  byte 1 another stage of the same map (the night versions m15-m25). Read by 0x62B714 and 0x62D910.
  Map 1-8 -> 1-8, map 9 -> 8 (the Arena), 10 -> 11, 11 -> 10, 12 -> 11, 13-15 -> 12-14.
- Right after it (VA 0xBEAF0E), 18 bytes: quest map -> number of the map in the placement table
  (map 9 and 10 -> 9, the event Water Arena; 16-17 = 0xFF). Read by 0x627E7C and 0x637244.
- Stage loading (0x646770): stage numbers below 28 go through a remap table at 0xC42588 (15-25 -> the
  day stage folders), then 26 -> "mura" (Moga Village: mura-a00..a02, collision g00/w00) and 27 ->
  "minato" (Port Tanzia: minato-a00, a01), else "m%2.2dd".
- No quest of the game uses map 9 (365 base quests; maps 9 and 10 absent). The pack's experiment sets
  map 9 to (26, 26) or (27, 27) and its placement number to 8 (the Arena, which the pack gives to every
  large monster). Box of the wall collision of each hub area: Village a00 x -3272..3278, z -1163..2739;
  a01 x -462..336, z -1081..778; a02 x -1750..1896, z -1232..1244; Port a00 x -2712..1846, z
  -2820..1719; a01 x -2911..583, z -2326..135. Not tried in the game.

## What makes a monster (for a future comparison with MHP3rd)
Each large monster is `romfs/arc/enemy/emNNN.arc` (MT Framework ARC, zlib), about 90-170 files:
| Part | Files (magic) | Notes |
|---|---|---|
| Model | MOD (meshes: body, tail and broken parts), MRL (materials), TEX (textures, BM/NM) | e.g. Zinogre: 17 MOD, 27 TEX |
| Animations | LMT `mot_emNNN_000/100/200` (1.5-2.3 MB, by far the largest part), EAN (texture/UV animations) | |
| Effects | EFL (particles), DMEM | |
| Sounds | MSS (`emNNN`), ESQ (sound sequences) | |
| Hit boxes | HTD `em_hitdata00`, HTS `em_hitsize00`, BDD `em_body00`/`em_cambody00` | |
| Stats | EMS `em_status00` | |
| Attack commands | EMC `em_cmd00` | per-attack parameters |
| Map data | EMM `em_mappos00`, EAR `em_arearoute00`, EMT `em_turnpos00`, EML `em_landing00`, EMG `em_gmv00` | what the Monster pack copies |
| **Behaviour (AI)** | **not in the archive**: compiled code in code.bin, one C++ class per base species (`uEm002` ... `uEm075`, 41 classes; subspecies reuse their base species' class) | |

So a model and its animations can in principle be swapped file by file, but a new monster needs its own
behaviour code in code.bin (or a reused class whose animation numbers match). MHP3rd (PSP) uses a
different engine and file formats: its models and motions would have to be converted, and its
behaviour rewritten for this engine. Not a task for this editor.
