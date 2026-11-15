"""Tests for the updater (mhqe/updater.py): it must replace program files only, keep every file of
the user, save copies first, and put the old version back on failure or on request. No network:
the online part is tried by hand (MHQE_NET=1 runs a real check against GitHub)."""
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mhqe import updater as U  # noqa: E402


def make_zip(files: dict, top="MH3U-Custom-Quest-Editor-main") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(top + "/", "")
        for name, data in files.items():
            z.writestr(f"{top}/{name}", data)
    return buf.getvalue()


def program(version, extra=None):
    files = {"mh3u_quest_editor.py": b"run()", "mhqe/__init__.py": f'__version__ = "{version}"\n'.encode(),
             "mhqe/app.py": f"# app {version}".encode(), "data/table.json": b"{}"}
    files.update(extra or {})
    return files


class Updater(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        for rel, data in program("1.0.0", {"mhqe/old_only.py": b"x"}).items():
            p = self.dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        self.user = {"settings.json": b'{"theme": "night"}', "custom_supply.json": b"[1]",
                     "library/00001_My_quest.mh3uq": b"QTDS mine", "workspace/rom_edits/q_11120.quest": b"QTDS edit",
                     "workspace/roaming_lists.json": b"{}", "backups/original/quest1": b"save",
                     "output/MH3U_Quest_Mod/romfs/quest/eu/quest.list": b"XFS"}
        for rel, data in self.user.items():
            p = self.dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        (self.dir / "mhqe" / "__pycache__").mkdir()
        (self.dir / "mhqe" / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"old")

    def user_files_intact(self):
        for rel, data in self.user.items():
            self.assertEqual((self.dir / rel).read_bytes(), data, rel)

    def test_versions(self):
        self.assertTrue(U.newer("1.10.0", "1.9.3"))
        self.assertTrue(U.newer("v1.6.1", "1.6.0"))
        self.assertFalse(U.newer("1.6.0", "1.6.0"))
        log = "# Changelog\n\n## 1.7.0\n\n* B\n\n## 1.6.1\n\n* A\n\n## 1.6.0\n\n* old\n"
        self.assertEqual(U.changes_since(log, "1.6.0"), "## 1.7.0\n\n* B\n\n## 1.6.1\n\n* A")

    def test_update_keeps_user_files_and_can_be_undone(self):
        new = program("1.1.0", {"mhqe/new_module.py": b"y", "settings.json": b"{}",       # a shipped settings file
                                "library/sample.mh3uq": b"no"})                          # must never be written
        files = U.read_zip(make_zip(new), "1.1.0")
        self.assertNotIn("settings.json", files)
        self.assertNotIn("library/sample.mh3uq", files)
        with mock.patch.object(U, "__version__", "1.0.0"):
            bdir = U.apply(self.dir, files, "1.1.0")
        self.user_files_intact()
        self.assertFalse((self.dir / "library" / "sample.mh3uq").exists())
        self.assertEqual((self.dir / "mhqe/app.py").read_bytes(), b"# app 1.1.0")
        self.assertEqual((self.dir / "mhqe/new_module.py").read_bytes(), b"y")
        self.assertTrue((self.dir / "mhqe/old_only.py").exists())            # left alone
        self.assertFalse((self.dir / "mhqe" / "__pycache__").exists())
        with zipfile.ZipFile(bdir / "your_data.zip") as z:
            names = set(z.namelist())
        self.assertTrue({"settings.json", "custom_supply.json", "library/00001_My_quest.mh3uq",
                         "workspace/rom_edits/q_11120.quest", "workspace/roaming_lists.json"} <= names)
        self.assertEqual((bdir / "program" / "mhqe/app.py").read_bytes(), b"# app 1.0.0")
        folder, info = U.last_update(self.dir)
        self.assertEqual(folder, bdir)
        self.assertEqual((info["from"], info["to"]), ("1.0.0", "1.1.0"))
        U.undo(self.dir, bdir)
        self.assertEqual((self.dir / "mhqe/app.py").read_bytes(), b"# app 1.0.0")
        self.assertFalse((self.dir / "mhqe/new_module.py").exists())
        self.user_files_intact()
        self.assertIsNone(U.last_update(self.dir))

    def test_failure_half_way_puts_the_old_version_back(self):
        files = U.read_zip(make_zip(program("1.1.0", {"zz_last.py": b"z"})), "1.1.0")
        real = Path.write_bytes
        calls = []

        def flaky(self_, data):
            calls.append(self_)
            if len(calls) == 3:
                raise OSError("disk full")
            return real(self_, data)
        with mock.patch.object(Path, "write_bytes", flaky):
            with self.assertRaises(U.UpdateError):
                U.apply(self.dir, files, "1.1.0")
        self.assertEqual((self.dir / "mhqe/app.py").read_bytes(), b"# app 1.0.0")
        self.assertEqual((self.dir / "mhqe/__init__.py").read_bytes(), b'__version__ = "1.0.0"\n')
        self.assertFalse((self.dir / "zz_last.py").exists())
        self.user_files_intact()

    def test_bad_downloads_are_refused(self):
        with self.assertRaises(U.UpdateError):
            U.read_zip(b"not a zip")
        with self.assertRaises(U.UpdateError):
            U.read_zip(make_zip({"README.md": b"x"}))                          # not the editor
        with self.assertRaises(U.UpdateError):
            U.read_zip(make_zip(program("1.1.0")), "1.2.0")                   # not the version announced
        with self.assertRaises(U.UpdateError):
            U.read_zip(make_zip(program("1.1.0", {"../evil.py": b"x"})))

    def test_git_copies_are_not_updated(self):
        (self.dir / ".git").mkdir()
        self.assertIn("git", U.can_update(self.dir))
        with self.assertRaises(U.UpdateError):
            U.apply(self.dir, U.read_zip(make_zip(program("1.1.0"))), "1.1.0")

    @unittest.skipUnless(os.environ.get("MHQE_NET"), "MHQE_NET not set (online check)")
    def test_online(self):
        latest = U.find_latest()
        self.assertTrue(U.parse_version(latest["version"]))
        files = U.read_zip(U.download(latest["ref"]), latest["version"])
        self.assertIn("mhqe/updater.py" if U.newer(latest["version"], "1.6.0") else "mhqe/app.py", files)
        print("\nonline:", json.dumps({k: v for k, v in latest.items() if k != "notes"}), len(files), "files")


if __name__ == "__main__":
    unittest.main()
