"""Finding the game's romfs folder from the folder a user picked (Settings > Choose the romfs
folder). A US player was told "This does not look like the game's romfs folder" after picking the
folder of a dump instead of the romfs folder itself."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mhqe.project import RomSource, find_romfs, romfs_region  # noqa: E402

ARC = os.environ.get("MHQE_US_ARC")          # a real quest00.arc of the US version (optional)


def fake_romfs(root: Path, region: str) -> Path:
    for d in ("sound", "movie", "arc/enemy", f"quest/{region}"):
        (root / d).mkdir(parents=True, exist_ok=True)
    arc = root / "arc" / "quest" / region
    arc.mkdir(parents=True, exist_ok=True)
    if ARC and region == "us":
        shutil.copy(ARC, arc / "quest00.arc")
    else:
        (arc / "quest00.arc").write_bytes(b"ARC\0")
    return root


class FindRomfs(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_romfs_itself(self):
        r = fake_romfs(self.tmp / "MH3U_US" / "romfs", "us")
        self.assertEqual(find_romfs(r), r)
        self.assertEqual(romfs_region(r), "us")

    def test_folder_above(self):
        r = fake_romfs(self.tmp / "MH3U_US" / "romfs", "us")
        (self.tmp / "MH3U_US" / "exefs").mkdir()
        self.assertEqual(find_romfs(self.tmp / "MH3U_US"), r)

    def test_dump_folders(self):
        # Citra / Azahar dump: dump/romfs/<title id>/ (with or without one more 'romfs' level)
        a = fake_romfs(self.tmp / "dump" / "romfs" / "00040000000AE400", "us")
        self.assertEqual(find_romfs(self.tmp / "dump"), a)
        b = fake_romfs(self.tmp / "other" / "00040000000AE400" / "romfs", "us")
        self.assertEqual(find_romfs(self.tmp / "other"), b)
        c = fake_romfs(self.tmp / "tool" / "ExtractedRomFS", "us")
        self.assertEqual(find_romfs(self.tmp / "tool"), c)

    def test_folder_inside(self):
        r = fake_romfs(self.tmp / "game" / "romfs", "us")
        self.assertEqual(find_romfs(r / "arc"), r)
        self.assertEqual(find_romfs(r / "arc" / "quest" / "us"), r)

    def test_both_versions(self):
        eu = fake_romfs(self.tmp / "dump" / "romfs" / "00040000000B1D00", "eu")
        us = fake_romfs(self.tmp / "dump" / "romfs" / "00040000000AE400", "us")
        self.assertEqual(find_romfs(self.tmp / "dump", prefer="us"), us)
        self.assertEqual(find_romfs(self.tmp / "dump", prefer="eu"), eu)

    def test_nothing(self):
        (self.tmp / "empty" / "a" / "b").mkdir(parents=True)
        self.assertIsNone(find_romfs(self.tmp / "empty"))

    @unittest.skipUnless(ARC, "MHQE_US_ARC not set")
    def test_us_game_loads_from_the_dump_folder(self):
        fake_romfs(self.tmp / "dump" / "romfs" / "00040000000AE400", "us")
        rom = RomSource(find_romfs(self.tmp / "dump"), workspace=self.tmp / "ws", load_edits=False)
        self.assertEqual(rom.region_dir, "us")
        self.assertEqual(len(rom.quests), 365)


if __name__ == "__main__":
    unittest.main()
